# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/panels/paint/collapse_button.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
extends Button


@export var node : Node


func _ready():
	if node:
		button_pressed = node.visible

func _on_toggled(toggled_on : bool):
	if node:
		node.visible = toggled_on
