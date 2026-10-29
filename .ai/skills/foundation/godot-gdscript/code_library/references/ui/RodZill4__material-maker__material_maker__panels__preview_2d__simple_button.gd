# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/panels/preview_2d/simple_button.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
class_name SimpleButton
extends Button

@export var icon_name := ""

func _ready() -> void:
	icon = get_theme_icon(icon_name, "MM_Icons")
