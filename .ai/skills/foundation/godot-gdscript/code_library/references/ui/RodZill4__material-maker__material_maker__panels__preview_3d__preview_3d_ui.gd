# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/panels/preview_3d/preview_3d_ui.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends HBoxContainer

@export var target : NodePath = ".."
var target_node

func _ready() -> void:
	target_node = get_node(target)

	$Model.icon = get_theme_icon("model", "MM_Icons")
	$Environment.icon = get_theme_icon("environment", "MM_Icons")
