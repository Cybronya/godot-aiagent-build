# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/mono/2.5d/assets/ui/control_hints.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Control

func _process(_delta):
	if Input.is_action_just_pressed(&"toggle_control_hints"):
		visible = not visible
