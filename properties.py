import bpy

def get_area_index(context):
	"""Get the current area index"""
	area = context.area
	if not area:
		return -1
	
	for i, a in enumerate(context.screen.areas):
		if a == area:
			return i
	return -1

def get_area_property_name(area_index, prop_name):
	"""Generate area-specific property name"""
	return f"dof_viz_{area_index}_{prop_name}"

def get_area_dof_setting(context, prop_name, default=False):
	"""Get DoF setting for current area"""
	area_index = get_area_index(context)
	if area_index == -1:
		return default
	
	prop_name = get_area_property_name(area_index, prop_name)
	return getattr(context.window_manager, prop_name, default)

def set_area_dof_setting(context, prop_name, value):
	"""Set DoF setting for current area"""
	area_index = get_area_index(context)
	if area_index == -1:
		return
	
	full_prop_name = get_area_property_name(area_index, prop_name)
	
	# Create the property if it doesn't exist
	if not hasattr(context.window_manager, full_prop_name):
		setattr(bpy.types.WindowManager, full_prop_name, bpy.props.BoolProperty(default=False))
	
	setattr(context.window_manager, full_prop_name, value)

# --- UI & Property Group ---
class DofVizSettings(bpy.types.PropertyGroup):
	# Keep these as dummy properties for backward compatibility
	# The actual values are stored per-area in WindowManager
	show_depth_of_field: bpy.props.BoolProperty(
		name="DoF gradients",
		description="Toggle the DoF gradient visualization on or off",
		default=False
	)
	show_focal_plane: bpy.props.BoolProperty(
		name="Focal Plane",
		description="Toggle the focal plane visualization on or off",
		default=False
	)
	show_text_info: bpy.props.BoolProperty(
		name="Text Info",
		description="Toggle the DoF text information on or off",
		default=False
	)
	dof_limits: bpy.props.BoolProperty(
		name="DoF Limits",
		description="Toggle the visualization of the near and far DoF planes",
		default=False
	)
