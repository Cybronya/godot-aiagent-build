# Source:  https://github.com/HungryProton/scatter/blob/main/addons/proton_scatter/src/stack/inspector_plugin/ui/presets/preset.gd
# Repo:    HungryProton/scatter (star 3017) | License: MIT | Collected: 2026-10-28
# Commit:  main
@tool
extends Button


signal load_preset
signal delete_preset


@onready var _label: Label = $MarginContainer/HBoxContainer/Label


func set_preset_name(text) -> void:
	_label.text = text


func _on_pressed() -> void:
	load_preset.emit()


func _on_delete() -> void:
	delete_preset.emit()
