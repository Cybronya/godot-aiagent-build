# Source:  https://github.com/HungryProton/scatter/blob/main/addons/proton_scatter/src/stack/inspector_plugin/ui/modifier/toggle_button.gd
# Repo:    HungryProton/scatter (star 3017) | License: MIT | Collected: 2026-10-28
# Commit:  7198cc00078e
@tool
extends Button


@export var default_icon: Texture
@export var pressed_icon: Texture


func _ready() -> void:
	toggled.connect(_on_toggled)
	_on_toggled(button_pressed)


func _on_toggled(pressed: bool) -> void:
	if pressed:
		icon = pressed_icon
	else:
		icon = default_icon
