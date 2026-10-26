# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/misc/2.5d/assets/ui/control_hints.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Control


func _input(input_event: InputEvent) -> void:
	if input_event.is_action_pressed(&"toggle_control_hints"):
		visible = not visible
