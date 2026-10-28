# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/panels/preview_2d/two_icon_toggle_button.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends Button

@export var icon_normal_name := ""
@export var icon_pressed_name := ""

func _ready() -> void:
	toggled.connect(_on_toggled)
	_on_toggled(button_pressed)


func _on_toggled(_toggled : bool = false):
	if button_pressed:
		icon = get_theme_icon(icon_pressed_name, "MM_Icons")
	else:
		icon = get_theme_icon(icon_normal_name, "MM_Icons")
