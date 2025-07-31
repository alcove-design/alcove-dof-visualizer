import bpy
from .properties import get_area_dof_setting, set_area_dof_setting
from . import handlers

class DOF_VIZ_OT_toggle_setting(bpy.types.Operator):
	"""Toggle DoF visualization setting for current area"""
	bl_idname = "dof_viz.toggle_setting"
	bl_label = "Toggle DoF Setting"
	bl_options = {'REGISTER'}
	
	setting_name: bpy.props.StringProperty()
	
	def execute(self, context):
		current_value = get_area_dof_setting(context, self.setting_name)
		new_value = not current_value
		set_area_dof_setting(context, self.setting_name, new_value)
		
		# Update handlers for this area
		handlers.update_handlers(context)
		
		# Force UI refresh
		for area in context.screen.areas:
			if area.type == 'VIEW_3D':
				area.tag_redraw()
		
		return {'FINISHED'}

def register():
	bpy.utils.register_class(DOF_VIZ_OT_toggle_setting)

def unregister():
	bpy.utils.unregister_class(DOF_VIZ_OT_toggle_setting)
