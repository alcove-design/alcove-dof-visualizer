import bpy
import gpu
import blf
from mathutils import Vector

from .batches import create_batches, update_specific_batches, create_single_batch
from .shaders import vertex_shader, fragment_shader
from .properties import get_area_index, get_area_dof_setting

import time

def timeit(func):
	def wrapper(*args, **kwargs):
		start = time.perf_counter()
		result = func(*args, **kwargs)
		end = time.perf_counter()
		print(f"{func.__name__} took {end - start:.6f} seconds")
		return result
	return wrapper

# --- Global State ---
dof_viz_state = {
	"area_handlers": {},  # area_index -> {"draw_handler": handler, "text_handler": handler}
	"depsgraph_handler": None,
	"shader": None,
	"mesh_batches": {},
	"info_data": {}  # Store calculated values for text display
}

def is_any_area_enabled():
	"""Check if any area has DoF visualization enabled"""
	for window in bpy.context.window_manager.windows:
		for area_index, area in enumerate(window.screen.areas):
			if area.type == 'VIEW_3D':
				# Check if any setting is enabled for this area
				if (get_area_dof_setting_by_index(area_index, "show_depth_of_field") or
					get_area_dof_setting_by_index(area_index, "show_focal_plane") or
					get_area_dof_setting_by_index(area_index, "show_dof_limits") or
					get_area_dof_setting_by_index(area_index, "show_text_info")):
					return True
	return False

def get_area_dof_setting_by_index(area_index, prop_name, default=False):
	"""Get DoF setting by area index"""
	if area_index == -1:
		return default

	from .properties import get_area_property_name
	prop_name = get_area_property_name(area_index, prop_name)
	return getattr(bpy.context.window_manager, prop_name, default)

def on_depsgraph_update(scene, depsgraph):
	"""
	Handler called when Blender's dependency graph updates (objects move, geometry changes, etc.).
	Performs selective batch updates to minimize performance impact by only recreating 
	batches for objects that actually changed geometry or visibility.
	"""

	if not dof_viz_state["area_handlers"] or not is_any_area_enabled():
		return

	# Track what actually changed to minimize work
	geometry_changed_objects = set()
	recreate_batches = False

	# 1. More granular geometry change detection
	for update in depsgraph.updates:
		if update.is_updated_geometry and hasattr(update, 'id') and update.id.bl_rna.identifier == 'Mesh':
			if hasattr(update.id, 'name'):
				geometry_changed_objects.add(update.id.name)
			else:
				# Fallback to full recreation if we can't identify the object
				recreate_batches = True
				break

	# 2. Check for object visibility or transform changes (cheaper than full recreation)
	if not recreate_batches and not geometry_changed_objects:
		current_visible_meshes = {obj.name for obj in bpy.context.visible_objects if obj.type == 'MESH'}
		cached_visible_meshes = dof_viz_state.get("cached_visible_meshes", set())
		
		if current_visible_meshes != cached_visible_meshes:
			# Only recreate batches for objects that changed visibility
			removed_objects = cached_visible_meshes - current_visible_meshes
			new_objects = current_visible_meshes - cached_visible_meshes
			
			if removed_objects:
				for obj_name in removed_objects:
					dof_viz_state["mesh_batches"].pop(obj_name, None)
			
			if new_objects:
				geometry_changed_objects.update(new_objects)
			
			dof_viz_state["cached_visible_meshes"] = current_visible_meshes

	# 3. Camera change detection (unchanged)
	if not recreate_batches and not geometry_changed_objects:
		current_active_camera = bpy.context.scene.camera
		if dof_viz_state.get("current_camera") != current_active_camera:
			recreate_batches = True

	# 4. Perform targeted updates
	if recreate_batches:
		create_batches(bpy.context, dof_viz_state)
		dof_viz_state["current_camera"] = bpy.context.scene.camera
	elif geometry_changed_objects:
		update_specific_batches(bpy.context, geometry_changed_objects, dof_viz_state)

	# Tag all relevant viewports for redraw
	for window in bpy.context.window_manager.windows:
		for area_index, area in enumerate(window.screen.areas):
			if area.type == 'VIEW_3D' and area_index in dof_viz_state["area_handlers"]:
				area.tag_redraw()

def update_handlers(context):
	"""
	Manage draw handlers based on current UI settings.
	Registers handlers for areas with enabled DoF visualization options,
	unregisters handlers for disabled areas, and manages the global depsgraph handler.
	"""

	area_index = get_area_index(context)
	if area_index == -1:
		return

	area_enabled = (get_area_dof_setting(context, "show_depth_of_field") or 
					get_area_dof_setting(context, "show_focal_plane") or 
					get_area_dof_setting(context, "show_dof_limits") or
					get_area_dof_setting(context, "show_text_info"))

	if area_enabled and area_index not in dof_viz_state["area_handlers"]:
		register_area_handlers(context, area_index)
	elif not area_enabled and area_index in dof_viz_state["area_handlers"]:
		unregister_area_handlers(area_index)

	# Manage global depsgraph handler
	any_area_enabled = is_any_area_enabled()
	if any_area_enabled and dof_viz_state["depsgraph_handler"] is None:
		dof_viz_state["depsgraph_handler"] = on_depsgraph_update
		if dof_viz_state["depsgraph_handler"] not in bpy.app.handlers.depsgraph_update_post:
			bpy.app.handlers.depsgraph_update_post.append(dof_viz_state["depsgraph_handler"])
	elif not any_area_enabled and dof_viz_state["depsgraph_handler"] is not None:
		if dof_viz_state["depsgraph_handler"] in bpy.app.handlers.depsgraph_update_post:
			bpy.app.handlers.depsgraph_update_post.remove(dof_viz_state["depsgraph_handler"])
		dof_viz_state["depsgraph_handler"] = None

# --- Handler Registration ---
def register_area_handlers(context, area_index):
	"""
	Register draw handlers for a specific 3D viewport area.
	Creates both overlay drawing and text display handlers, and ensures
	GPU batches are available for rendering.
	"""

	state = dof_viz_state
	if area_index in state["area_handlers"]:
		return

	# Create batches if not already created
	if not state["mesh_batches"]:
		create_batches(context, dof_viz_state)

	# Register handlers for this specific area
	draw_handler = bpy.types.SpaceView3D.draw_handler_add(
		lambda ctx: draw_dof_overlay(ctx, area_index), 
		(context,), 'WINDOW', 'POST_VIEW'
	)
	text_handler = bpy.types.SpaceView3D.draw_handler_add(
		lambda ctx: draw_dof_info_text(ctx, area_index), 
		(context,), 'WINDOW', 'POST_PIXEL'
	)

	state["area_handlers"][area_index] = {
		"draw_handler": draw_handler,
		"text_handler": text_handler
	}

	print(f"DoF Visualizer: Handlers Registered for area {area_index}")

def unregister_area_handlers(area_index):
	"""
	Remove draw handlers for a specific area and clean up associated resources.
	If no areas remain active, clears global mesh batches and shader state.
	"""

	state = dof_viz_state
	if area_index not in state["area_handlers"]:
		return

	handlers = state["area_handlers"][area_index]

	if handlers["draw_handler"] is not None:
		bpy.types.SpaceView3D.draw_handler_remove(handlers["draw_handler"], 'WINDOW')
	if handlers["text_handler"] is not None:
		bpy.types.SpaceView3D.draw_handler_remove(handlers["text_handler"], 'WINDOW')

	del state["area_handlers"][area_index]

	# Clean up global state if no areas are active
	if not state["area_handlers"]:
		state["mesh_batches"].clear()
		state["shader"] = None

	print(f"DoF Visualizer: Handlers Unregistered for area {area_index}")

def unregister_all_handlers():
	"""Unregister all handlers (used during addon unregister)"""
	state = dof_viz_state

	# Unregister all area handlers
	for area_index in list(state["area_handlers"].keys()):
		unregister_area_handlers(area_index)

	# Unregister depsgraph handler
	if state["depsgraph_handler"] is not None:
		if state["depsgraph_handler"] in bpy.app.handlers.depsgraph_update_post:
			bpy.app.handlers.depsgraph_update_post.remove(state["depsgraph_handler"])
		state["depsgraph_handler"] = None

	print("DoF Visualizer: All Handlers Unregistered")

def calculate_dof_info(context):
	"""Calculate DoF parameters using a physically-based model and store in state"""

	scene_cam = context.scene.camera
	if not scene_cam or not scene_cam.data.dof.use_dof:
		dof_viz_state["info_data"] = {}
		return

	cam_data = scene_cam.data
	fstop = cam_data.dof.aperture_fstop
	focal_length_m = cam_data.lens / 1000.0
	sensor_width_m = cam_data.sensor_width / 1000.0

	focus_object = cam_data.dof.focus_object
	if focus_object:
		depsgraph = context.evaluated_depsgraph_get()
		cam_eval = scene_cam.evaluated_get(depsgraph)
		focus_object_eval = focus_object.evaluated_get(depsgraph)
		focus_distance = (cam_eval.matrix_world.translation - focus_object_eval.matrix_world.translation).length
	else:
		focus_distance = cam_data.dof.focus_distance

	dof_near, dof_far, hyperfocal = 0.0, float('inf'), float('inf')

	if fstop > 0 and focus_distance > 0:
		coc = sensor_width_m / 1500
		hyperfocal = (focal_length_m**2) / (fstop * coc) + focal_length_m

		s_minus_f = focus_distance - focal_length_m
		if s_minus_f > 0:
			if focus_distance >= hyperfocal:
				dof_far = float('inf')
			else:
				dof_far = (hyperfocal * focus_distance) / (hyperfocal - s_minus_f)

			dof_near = (hyperfocal * focus_distance) / (hyperfocal + s_minus_f)

	dof_viz_state["info_data"] = {
		"focus_distance": focus_distance,
		"dof_near": dof_near,
		"dof_far": dof_far,
		"hyperfocal": hyperfocal,
	}

def draw_dof_overlay(context, target_area_index):
	"""Draw DoF visualization overlay in the 3D viewport."""

	# Only draw if we're in the target area
	current_area_index = get_area_index(context)
	if current_area_index != target_area_index:
		return

	scene_cam = context.scene.camera
	if not scene_cam or not scene_cam.data.dof.use_dof:
		return

	if not context.space_data.overlay.show_overlays:
		return

	# Only draw in Solid viewport shading mode
	if context.space_data.shading.type != 'SOLID':
		return

	# Calculate DoF info
	calculate_dof_info(context)

	# Get the calculated values from state
	info_data = dof_viz_state.get("info_data", {})
	dof_near = info_data.get("dof_near", 0.0)
	dof_far = info_data.get("dof_far", float('inf'))
	focus_distance = info_data.get("focus_distance", 0.0)

	# Check area-specific settings
	area_show_dof = get_area_dof_setting_by_index(target_area_index, "show_depth_of_field")
	area_show_focal_plane = get_area_dof_setting_by_index(target_area_index, "show_focal_plane")
	area_show_limits = get_area_dof_setting_by_index(target_area_index, "show_dof_limits")

	if not area_show_dof and not area_show_focal_plane and not area_show_limits:
		return

	state = dof_viz_state
	scene_cam = context.scene.camera
	region_3d = context.space_data.region_3d
	if not scene_cam or not state["shader"] or not region_3d:
		return

	state["current_camera"] = scene_cam

	# --- Get Matrices ---
	viewport_view_matrix = region_3d.view_matrix
	viewport_projection_matrix = region_3d.window_matrix
	scene_camera_view_matrix = scene_cam.matrix_world.inverted()

	# --- GPU State & Uniforms ---
	frag_depth_offset = 0.000001
	camera_space_light_dir = Vector((-0.15, 0.15, 1.0)).normalized()
	light_direction = scene_cam.matrix_world.to_3x3() @ camera_space_light_dir
	light_direction.normalize()
	ambient_factor = 0.2

	original_blend = gpu.state.blend_get()
	original_depth_test = gpu.state.depth_test_get()
	gpu.state.blend_set('ALPHA')
	gpu.state.depth_test_set('LESS_EQUAL')
	gpu.state.face_culling_set('BACK')

	try:
		shader = state["shader"]
		shader.bind()
		shader.uniform_float("u_sceneCameraViewMatrix", scene_camera_view_matrix)
		# Pass the unified, physically-based values to the shader
		shader.uniform_float("u_dof_near_plane", dof_near)
		shader.uniform_float("u_dof_far_plane", dof_far)
		shader.uniform_float("u_focus_distance", focus_distance)

		# Define overlay colors
		shader.uniform_float("u_in_focus_color", (0.3, 0.8, 0.3, 0.7))
		shader.uniform_float("u_near_color", (0.05, 0.1, 1, 0.7))
		shader.uniform_float("u_far_color", (1, 0.08, 0.1, 0.7))
		shader.uniform_float("u_far_gradient_color", (0.95, 0.43, 0.17, 0.7))
		shader.uniform_float("u_focus_plane_color", (0.0, 0.8, 0.0, 0.7)) # Green, opaque for laser effect
		shader.uniform_float("u_frag_depth_offset", frag_depth_offset)
		shader.uniform_float("u_light_direction", light_direction)
		shader.uniform_float("u_ambient_factor", ambient_factor)

		# Dynamically adjust focus plane tolerance based on focus distance
		# This makes the lines appear thinner in miniature scenes and thicker in large scenes
		focus_plane_tolerance = max(0.001, min(0.1, focus_distance * 0.005)) # Clamped between 0.001 and 0.1
		shader.uniform_float("u_focus_plane_tolerance", focus_plane_tolerance)

		shader.uniform_bool("u_show_focal_plane", area_show_focal_plane)
		shader.uniform_bool("u_show_dof_limits", area_show_limits)
		shader.uniform_bool("u_show_depth_of_field", area_show_dof)

		camera_location = scene_cam.matrix_world.translation
		sorted_batches = sorted([
			((obj.matrix_world.translation - camera_location).length, obj, data)
			for name, data in state["mesh_batches"].items()
			if (obj := bpy.context.scene.objects.get(name)) and obj.visible_get()
		], key=lambda x: x[0], reverse=True)

		for _, obj, data in sorted_batches:
			model_matrix = obj.matrix_world
			mvp_matrix = viewport_projection_matrix @ viewport_view_matrix @ model_matrix
			shader.uniform_float("u_modelViewProjectionMatrix", mvp_matrix)
			shader.uniform_float("u_modelMatrix", model_matrix)
			data["batch"].draw(shader)
	finally:
		gpu.state.blend_set(original_blend)
		gpu.state.depth_test_set(original_depth_test)
		gpu.state.face_culling_set('NONE')

def draw_dof_info_text(context, target_area_index):
	"""Draw DoF information text in the viewport."""

	# Only draw if we're in the target area
	current_area_index = get_area_index(context)
	if current_area_index != target_area_index:
		return

	scene_cam = context.scene.camera
	if not scene_cam or not scene_cam.data.dof.use_dof:
		return

	if not context.space_data.overlay.show_overlays:
		return

	# Check area-specific text info setting
	if not get_area_dof_setting_by_index(target_area_index, "show_text_info"):
		return

	# Calculate DoF info
	calculate_dof_info(context)

	info_data = dof_viz_state.get("info_data")
	if not info_data:
		return

	font_id = 0
	dpi = bpy.context.preferences.system.dpi
	font_size = int(11 * bpy.context.preferences.view.ui_scale)
	blf.size(font_id, font_size)

	# --- Shadow Setup ---
	# Emulate Blender's default UI text shadow for readability
	blf.enable(font_id, blf.SHADOW)
	blf.shadow(font_id, 3, 0.0, 0.0, 0.0, 0.8) # 3-level blur, black, 80% alpha
	blf.shadow_offset(font_id, 1, -1)

	# Dynamic positioning
	x_margin = 15
	y_pos = context.region.height - 30
	line_height = (font_size + 5) * (dpi / 72)

	# Adjust position based on other visible overlays to prevent overlap
	if context.space_data.overlay.show_text:
		y_pos -= line_height * 5 # Approximate height for the default Text Info
	if context.space_data.overlay.show_stats:
		y_pos -= line_height * 8 # Approximate height for the Statistics overlay

	# Draw Title
	blf.position(font_id, x_margin, y_pos, 0)
	blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
	blf.draw(font_id, "DoF Visualizer Info")
	y_pos -= line_height * 1.5

	# Draw Data
	def format_dist(label, value):
		val_str = f"{value:.2f}m" if value is not None and value != float('inf') else "inf"
		return f"{label}: {val_str}"

	info_lines = [
		format_dist("Focus Distance", info_data.get("focus_distance")),
		format_dist("DoF Near", info_data.get("dof_near")),
		format_dist("DoF Far", info_data.get("dof_far")),
		format_dist("Hyperfocal", info_data.get("hyperfocal")),
	]

	blf.color(font_id, 1.0, 1.0, 1.0, 0.7)
	for line in info_lines:
		blf.position(font_id, x_margin, y_pos, 0)
		blf.draw(font_id, line)
		y_pos -= line_height
		
	# --- Cleanup ---
	blf.disable(font_id, blf.SHADOW)
