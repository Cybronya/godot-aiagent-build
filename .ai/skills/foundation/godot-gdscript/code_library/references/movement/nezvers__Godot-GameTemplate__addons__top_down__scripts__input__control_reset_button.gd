# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/input/control_reset_button.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
extends Button

@export var action_resource:ActionResource

func _pressed()->void:
	action_resource.reset_resource()
