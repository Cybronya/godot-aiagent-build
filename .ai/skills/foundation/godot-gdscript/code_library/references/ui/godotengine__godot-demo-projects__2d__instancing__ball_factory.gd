# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/instancing/ball_factory.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Node2D


@export var ball_scene: PackedScene = preload("res://ball.tscn")


func _unhandled_input(input_event: InputEvent) -> void:
	if input_event.is_echo():
		return

	if input_event is InputEventMouseButton and input_event.is_pressed():
		if input_event.button_index == MOUSE_BUTTON_LEFT:
			spawn(get_global_mouse_position())


func spawn(spawn_global_position: Vector2) -> void:
	var instance: Node2D = ball_scene.instantiate()
	instance.global_position = spawn_global_position
	add_child(instance)
