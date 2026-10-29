# Source:  https://github.com/bitbrain/pandora/blob/godot-4.x/addons/pandora/ui/editor/settings_dialog/dependency.gd
# Repo:    bitbrain/pandora (star 1129) | License: MIT | Collected: 2026-10-29
# Commit:  fa48e30e6609
@tool
class_name Dependency
extends PanelContainer

signal removed(dependency: Dictionary)

@onready var label: Label = $MarginContainer/HBoxContainer/Label

var dependency: Dictionary

func _ready() -> void:
	label.text = dependency["name"]

func _on_button_pressed() -> void:
	removed.emit(dependency)
	queue_free()
