# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/misc/multiple_windows/scenes/draggable_window/draggable_region.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Area2D


func _input_event(_viewport: Viewport, input_event: InputEvent, _shape_index: int) -> void:
	if input_event is InputEventMouseButton:
		if input_event.pressed:
			get_window().start_drag()
