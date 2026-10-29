# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/pong/logic/ceiling_floor.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Area2D

@export var _bounce_direction := 1

func _on_area_entered(area: Area2D) -> void:
	if area.name == "Ball":
		area.direction = (area.direction + Vector2(0, _bounce_direction)).normalized()
