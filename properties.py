import bpy

#############################################################
# 
# Per-Area Settings Management
# Functions for storing and retrieving DoF visualization 
# settings on a per-viewport basis using WindowManager
# 
#############################################################
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


#############################################################
# 
# Overlay Colors Customization
# Addon preferences for color modes (default, colorblind-friendly, custom)
# and individual color picker properties
# 
#############################################################
class DoFVisualizerPreferences(bpy.types.AddonPreferences):
	"""
	Addon preferences for DoF Visualizer color customization.
	Provides options for default, colorblind-friendly, or custom color palettes
	for the depth of field visualization overlays.
	"""
	bl_idname = __package__

	color_mode: bpy.props.EnumProperty(
		name="Color Mode",
		items=[
			('DEFAULT', "Default", "Standard colors"),
			('COLORBLIND', "Colorblind Friendly", "High contrast colors safe for colorblind users"), 
			('CUSTOM', "Custom", "Choose your own colors")
		],
		default='DEFAULT',
	)

	# Custom color properties (only shown when CUSTOM selected)
	custom_near_color: bpy.props.FloatVectorProperty(
		name="Near Blur", subtype='COLOR_GAMMA', size=4, default=(0.05, 0.1, 1.0, 0.7), min=0.0, max=1.0
	)
	custom_in_focus_color: bpy.props.FloatVectorProperty(
		name="In Focus", subtype='COLOR_GAMMA', size=4, default=(0.3, 0.8, 0.3, 0.7), min=0.0, max=1.0
	)
	custom_far_color: bpy.props.FloatVectorProperty(
		name="Far Blur", subtype='COLOR_GAMMA', size=4, default=(0.95, 0.43, 0.17, 0.7), min=0.0, max=1.0
	)
	custom_far_max_color: bpy.props.FloatVectorProperty(
		name="Far Max Blur", subtype='COLOR_GAMMA', size=4, default=(1.0, 0.08, 0.1, 0.7), min=0.0, max=1.0
	)
	custom_focal_plane_color: bpy.props.FloatVectorProperty(
		name="Focal Plane", subtype='COLOR_GAMMA', size=4, default=(0.0, 0.8, 0.0, 0.7), min=0.0, max=1.0
	)

	def draw(self, context):
		layout = self.layout

		# Radio button group for color mode
		row = layout.row(align=True)
		row.prop(self, "color_mode", expand=True)

		# Custom color pickers (only visible when CUSTOM selected)
		if self.color_mode == 'CUSTOM':
			box = layout.box()
			box.label(text="Custom Colors:")
			col = box.column()
			col.prop(self, "custom_near_color")
			col.prop(self, "custom_in_focus_color")
			col.prop(self, "custom_far_color")
			col.prop(self, "custom_far_max_color")
			col.prop(self, "custom_focal_plane_color")

def get_color_values(color_type):
	"""Get color values based on current mode"""
	addon_prefs = bpy.context.preferences.addons[__package__].preferences

	if addon_prefs.color_mode == 'DEFAULT':
		colors = {
			'near': (0.05, 0.1, 1.0, 0.7), # blue
			'in_focus': (0.3, 0.8, 0.3, 0.7), # green
			'far': (0.95, 0.43, 0.17, 0.7), # orange
			'far_max': (1.0, 0.08, 0.1, 0.7), # red
			'focal_plane': (1.0, 1.0, 1.0, 0.7) # white
		}
	elif addon_prefs.color_mode == 'COLORBLIND':
		colors = {
			'near': (0.13, 0.4, 0.67, 1), # blue
			'in_focus': (0.8, 0.8, 0.8, 0.7), # gray
			'far': (0.96, 0.65, 0.5, 1), # orange
			'far_max': (0.7, 0.09, 0.17, 0.8), # dark orange
			'focal_plane': (1.0, 1.0, 1.0, 0.9) # white
		}
	else:  # CUSTOM
		colors = {
			'near': addon_prefs.custom_near_color[:],
			'in_focus': addon_prefs.custom_in_focus_color[:],
			'far': addon_prefs.custom_far_color[:],
			'far_max': addon_prefs.custom_far_max_color[:],
			'focal_plane': addon_prefs.custom_focal_plane_color[:]
		}

	return colors[color_type]
