import bpy
import gpu
import numpy as np
import gpu.shader
from gpu_extras.batch import batch_for_shader

from .shaders import vertex_shader, fragment_shader


def create_batches(context, state):
	"""Create GPU batches for all visible mesh objects in the scene."""

	state["mesh_batches"].clear()
	if state["shader"] is None:
		try:
			# Try new method first (Blender 4.5+ Metal compatibility)
			shader_info = gpu.types.GPUShaderCreateInfo()
			shader_info.vertex_source(vertex_shader)
			shader_info.fragment_source(fragment_shader)

			# Define vertex inputs (based on batch creation)
			shader_info.vertex_in(0, 'VEC3', "pos")
			shader_info.vertex_in(1, 'VEC3', "normal")

			# Define vertex outputs (must match fragment inputs)
			shader_info.vertex_out(0, 'FLOAT', "v_scene_cam_depth")
			shader_info.vertex_out(1, 'VEC3', "v_normal")

			# Define fragment output
			shader_info.fragment_out(0, 'VEC4', "fragColor")

			# Define all uniforms used in handlers.py
			shader_info.push_constant('MAT4', "u_modelViewProjectionMatrix")
			shader_info.push_constant('MAT4', "u_modelMatrix")
			shader_info.push_constant('MAT4', "u_sceneCameraViewMatrix")
			shader_info.push_constant('FLOAT', "u_dof_near_plane")
			shader_info.push_constant('FLOAT', "u_dof_far_plane")
			shader_info.push_constant('FLOAT', "u_focus_distance")
			shader_info.push_constant('FLOAT', "u_aperture_fstop")
			shader_info.push_constant('FLOAT', "u_focal_length_m")
			shader_info.push_constant('FLOAT', "u_sensor_width")
			shader_info.push_constant('VEC4', "u_near_color")
			shader_info.push_constant('VEC4', "u_in_focus_color")
			shader_info.push_constant('VEC4', "u_far_color")
			shader_info.push_constant('VEC4', "u_far_max_color")
			shader_info.push_constant('VEC4', "u_focus_plane_color")
			shader_info.push_constant('FLOAT', "u_frag_depth_offset")
			shader_info.push_constant('VEC3', "u_light_direction")
			shader_info.push_constant('FLOAT', "u_ambient_factor")
			shader_info.push_constant('FLOAT', "u_focus_plane_tolerance")
			shader_info.push_constant('BOOL', "u_show_focal_plane")
			shader_info.push_constant('BOOL', "u_show_dof_limits")
			shader_info.push_constant('BOOL', "u_show_depth_of_field")

			state["shader"] = gpu.shader.create_from_info(shader_info)
		except (AttributeError, Exception):
			if hasattr(gpu.types, 'GPUShader'):
				# Fallback for older Blender versions
				state["shader"] = gpu.types.GPUShader(vertex_shader, fragment_shader)
			else:
				raise RuntimeError("Unable to create shader: neither new Metal API nor legacy GPUShader are available")

	depsgraph = context.evaluated_depsgraph_get()
	visible_meshes = {obj.name for obj in context.visible_objects if obj.type == 'MESH'}

	# Process objects in parallel-friendly way
	for obj in context.visible_objects:
		if obj.type == 'MESH' and obj.data:
			create_single_batch(obj, depsgraph, state)

	# Cache the current visible meshes for comparison
	state["cached_visible_meshes"] = visible_meshes

def update_specific_batches(context, changed_objects, state):
	"""Update GPU batches only for objects that have changed geometry."""

	depsgraph = context.evaluated_depsgraph_get()

	for obj_name in changed_objects:
		obj = bpy.context.scene.objects.get(obj_name)
		if obj and obj.type == 'MESH' and obj.visible_get():
			create_single_batch(obj, depsgraph, state)

def create_single_batch(obj, depsgraph, state):
	"""Create a single GPU batch for the given object with optimizations."""

	try:
		obj_eval = obj.evaluated_get(depsgraph)
		mesh = obj_eval.to_mesh()
	except:
		mesh = obj.data

	if not mesh.vertices or not mesh.loops:
		if 'to_mesh_clear' in dir(obj_eval): 
			obj_eval.to_mesh_clear()
		return

	# Pre-allocate arrays with correct size
	vertex_count = len(mesh.vertices)
	vertex_positions = np.empty(vertex_count * 3, dtype=np.float32)
	vertex_normals = np.empty(vertex_count * 3, dtype=np.float32)

	# Use foreach_get for faster data access
	mesh.vertices.foreach_get("co", vertex_positions)
	mesh.vertices.foreach_get("normal", vertex_normals)

	# Reshape in-place
	vertex_positions.shape = (-1, 3)
	vertex_normals.shape = (-1, 3)

	# Calculate triangles once
	mesh.calc_loop_triangles()
	triangle_count = len(mesh.loop_triangles)

	if triangle_count == 0:
		if 'to_mesh_clear' in dir(obj_eval): 
			obj_eval.to_mesh_clear()
		return

	# Pre-allocate triangle indices
	loop_triangle_indices = np.empty(triangle_count * 3, dtype=np.int32)
	mesh.loop_triangles.foreach_get("vertices", loop_triangle_indices)

	# Direct indexing for triangle data
	tris_vertices = vertex_positions[loop_triangle_indices]
	tris_normals = vertex_normals[loop_triangle_indices]

	# Create batch
	batch = batch_for_shader(
		state["shader"], 'TRIS', 
		{"pos": tris_vertices, "normal": tris_normals}
	)

	state["mesh_batches"][obj.name] = {
		"batch": batch,
		"matrix": obj.matrix_world
	}

	if 'to_mesh_clear' in dir(obj_eval): 
		obj_eval.to_mesh_clear()
