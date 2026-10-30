# Source:  https://github.com/MrEliptik/godot_experiments/blob/master/2D/polygon_tools/scenes/demo_scene/ball_spawner.gd
# Repo:    MrEliptik/godot_experiments (star 1034) | License: MIT | Collected: 2026-10-29
# Commit:  4baec7290110
extends Node

@export var ball_scene: PackedScene = preload("res://scenes/ball/ball.tscn")

@onready var parent: Node2D = get_parent()

func start() -> void:
	$Timer.start()

func spawn_ball() -> void:
	var instance = ball_scene.instantiate()
	parent.call_deferred("add_child", instance)
	await instance.ready
	var viewport_size: Vector2 = get_viewport().get_visible_rect().size
	instance.global_position = Vector2(randf_range(0, viewport_size.x), -150.0)

func _on_timer_timeout():
	spawn_ball()
