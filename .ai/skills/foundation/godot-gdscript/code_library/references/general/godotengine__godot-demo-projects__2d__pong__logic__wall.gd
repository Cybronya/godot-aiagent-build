# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/pong/logic/wall.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Area2D

func _on_wall_area_entered(area: Area2D) -> void:
	if area.name == "Ball":
		# Ball went out of bounds, reset.
		area.reset()
