import bpy
import rna_keymap_ui

class AddonPreferences(bpy.types.AddonPreferences):
	bl_idname = __package__

	def draw(self, context):
		layout = self.layout
		col = layout.column()
		self.draw_preferences(context, col)

	def draw_preferences(self, context, col):
		row = col.row()
		row.label(text = "", icon = "EVENT_CTRL")
		row.label(text = "HotKey")

		wm = context.window_manager
		kc = wm.keyconfigs.user
		  
		property_editor_reg_location = "3D View"
		km = kc.keymaps[property_editor_reg_location]
		col.label(text="3D View")
		kmi = get_hotkey_entry_item(km, 'screen.toggle_references_overlays', '')
		if kmi:
			col.context_pointer_set("keymap", km)
			rna_keymap_ui.draw_kmi([], kc, km, kmi, col, 0)
			col.separator()
		else:
			col.label(text="No hotkey entry found")
			col.operator('references_overlays.add_hotkey', text = "Add hotkey entry", icon = 'ZOOM_IN')
		kmi = get_hotkey_entry_item(km, 'screen.toggle_lock_references_overlays', '')
		if kmi:
			col.context_pointer_set("keymap", km)
			rna_keymap_ui.draw_kmi([], kc, km, kmi, col, 0)
			col.separator()
		else:
			col.label(text="No hotkey entry found")
			col.operator('references_overlays.add_hotkey', text = "Add hotkey entry", icon = 'ZOOM_IN')
		kmi = get_hotkey_entry_item(km, 'screen.toggle_grayscale_references_overlays', '')
		if kmi:
			col.context_pointer_set("keymap", km)
			rna_keymap_ui.draw_kmi([], kc, km, kmi, col, 0)
			col.separator()
		else:
			col.label(text="No hotkey entry found")
			col.operator('references_overlays.add_hotkey', text = "Add hotkey entry", icon = 'ZOOM_IN')
		kmi = get_hotkey_entry_item(km, 'screen.paste_reference', '')
		if kmi:
			col.context_pointer_set("keymap", km)
			rna_keymap_ui.draw_kmi([], kc, km, kmi, col, 0)
			col.separator()
		else:
			col.label(text="No hotkey entry found")
			col.operator('references_overlays.add_hotkey', text = "Add hotkey entry", icon = 'ZOOM_IN')

def get_hotkey_entry_item(km, kmi_name, kmi_value):
	for i, km_item in enumerate(km.keymap_items):
		if km.keymap_items.keys()[i] == kmi_name:
			return km_item
	return None

classes = (
	 AddonPreferences,
)

def register():
	for cls in classes:
		bpy.utils.register_class(cls)

def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
