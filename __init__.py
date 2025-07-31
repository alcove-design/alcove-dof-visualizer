bl_info = {
	"name": "Alcove DoF Visualizer",
	"author": "Alcove design - Mehdi El Fadil",
	"version": (1, 0),
	"blender": (4, 2, 0),
	"location": "View3D > Overlays Popover",
	"description": "Adds a real-time depth of field overlay and text info",
	"category": "3D View",
}

import bpy
from . import properties, ui, handlers, operators

classes = (
	properties.DofVizSettings,
)

@bpy.app.handlers.persistent
def load_post_handler(dummy):
	"""Re-register handlers after file load if settings are enabled"""
	# Clean up any existing dynamic properties and handlers
	cleanup_dynamic_properties()
	handlers.unregister_all_handlers()

def cleanup_dynamic_properties():
	"""Clean up all dynamic area-specific properties"""
	wm = bpy.context.window_manager
	props_to_remove = []

	for prop_name in dir(wm):
		if prop_name.startswith("dof_viz_"):
			props_to_remove.append(prop_name)

	for prop_name in props_to_remove:
		try:
			delattr(wm, prop_name)
		except:
			pass

def register():
	operators.register()
	for cls in classes:
		bpy.utils.register_class(cls)
	bpy.types.Scene.dof_viz_settings = bpy.props.PointerProperty(type=properties.DofVizSettings)
	bpy.types.VIEW3D_PT_overlay_motion_tracking.append(ui.draw_dof_viz_checkbox)
	bpy.app.handlers.load_post.append(load_post_handler)

def unregister():
	handlers.unregister_all_handlers()
	cleanup_dynamic_properties()
	bpy.types.VIEW3D_PT_overlay_motion_tracking.remove(ui.draw_dof_viz_checkbox)
	if load_post_handler in bpy.app.handlers.load_post:
		bpy.app.handlers.load_post.remove(load_post_handler)
	del bpy.types.Scene.dof_viz_settings
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
	operators.unregister()
