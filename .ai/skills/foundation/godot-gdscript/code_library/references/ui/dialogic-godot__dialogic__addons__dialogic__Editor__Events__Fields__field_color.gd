# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Editor/Events/Fields/field_color.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  main
@tool
extends DialogicVisualEditorField

## Event block field for color values.

#region MAIN METHODS
################################################################################

func _ready() -> void:
	self.color_changed.connect(_on_value_changed)


func _load_display_info(info:Dictionary) -> void:
	self.edit_alpha = info.get("edit_alpha", true)


func _set_value(value:Variant) -> void:
	if value is Color:
		self.color = Color(value)

#endregion


#region SIGNAL METHODS
################################################################################

func _on_value_changed(value: Color) -> void:
	value_changed.emit(property_name, value)

#endregion
