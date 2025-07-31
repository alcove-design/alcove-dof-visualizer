from .properties import get_area_index, get_area_dof_setting

def draw_dof_viz_checkbox(self, context):
	layout = self.layout
	if context.space_data.shading.type in {'SOLID', 'MATERIAL', 'TEXTURED'}:
		# Check if we're in a valid 3D viewport area
		area_index = get_area_index(context)
		if area_index == -1:
			return
		
		dof_settings = context.scene.dof_viz_settings
		layout.separator()
		layout.label(text="Depth of Field")

		cam = context.scene.camera
		is_dof_enabled = cam and cam.data.dof.use_dof
		sub_layout = layout.column()
		sub_layout.active = is_dof_enabled

		# Get area-specific settings for display
		show_gradient = get_area_dof_setting(context, "show_depth_of_field")
		show_focal = get_area_dof_setting(context, "show_focal_plane")
		show_text = get_area_dof_setting(context, "show_text_info")
		show_limits = get_area_dof_setting(context, "show_dof_limits")

		# Use custom operators to handle area-specific toggling
		row = sub_layout.row(align=True)
		text_op = row.operator("dof_viz.toggle_setting", text="Text Info", depress=show_text)
		text_op.setting_name = "show_text_info"

		gradient_op = row.operator("dof_viz.toggle_setting", text="Gradient", depress=show_gradient)
		gradient_op.setting_name = "show_depth_of_field"

		row = sub_layout.row(align=True)
		focal_op = row.operator("dof_viz.toggle_setting", text="Focal Plane", depress=show_focal)
		focal_op.setting_name = "show_focal_plane"
		
		limits_op = row.operator("dof_viz.toggle_setting", text="DoF Limits", depress=show_limits)
		limits_op.setting_name = "show_dof_limits"
