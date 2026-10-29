# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/voxel/menu/main/splash_text.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Control

var time := 0.0

func _process(delta: float) -> void:
	time += delta
	scale = Vector2.ONE * (1 - abs(sin(time * 4)) / 4)
