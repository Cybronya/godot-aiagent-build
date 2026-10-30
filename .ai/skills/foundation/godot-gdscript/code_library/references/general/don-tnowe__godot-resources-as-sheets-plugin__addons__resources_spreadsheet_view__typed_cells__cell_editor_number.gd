# Source:  https://github.com/don-tnowe/godot-resources-as-sheets-plugin/blob/master/addons/resources_spreadsheet_view/typed_cells/cell_editor_number.gd
# Repo:    don-tnowe/godot-resources-as-sheets-plugin (star 1031) | License: MIT | Collected: 2026-10-29
# Commit:  3363e0d2136c
extends ResourceTablesCellEditor


func can_edit_value(value, type, property_hint, column_index) -> bool:
	return type == TYPE_FLOAT or type == TYPE_INT


func to_text(value) -> String:
	return str(value)


func from_text(text : String):
	return text.to_float()
