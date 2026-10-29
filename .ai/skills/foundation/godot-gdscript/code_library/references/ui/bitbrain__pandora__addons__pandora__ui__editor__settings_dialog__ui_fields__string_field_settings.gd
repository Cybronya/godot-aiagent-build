# Source:  https://github.com/bitbrain/pandora/blob/godot-4.x/addons/pandora/ui/editor/settings_dialog/ui_fields/string_field_settings.gd
# Repo:    bitbrain/pandora (star 1129) | License: MIT | Collected: 2026-10-29
# Commit:  fa48e30e6609
@tool
class_name StringFieldSettings
extends VBoxContainer

signal updated(property_field: Dictionary)

@onready var label: Label = $Label
@onready var check_button: CheckButton = $HBoxContainer/CheckButton

var property_field : Dictionary : set = set_property_field

func set_property_field(field: Dictionary) -> void:
	property_field = field
	_update_field_settings()

func _update_field_settings() -> void:
	label.text = property_field["name"] + " Settings"
	check_button.button_pressed = property_field["enabled"]

func _on_check_button_toggled(toggled_on: bool) -> void:
	property_field["enabled"] = toggled_on
	updated.emit(property_field)
