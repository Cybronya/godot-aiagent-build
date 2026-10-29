# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/loading/autoload/scene_a.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Panel

func _on_goto_scene_pressed() -> void:
	global.goto_scene("res://scene_b.tscn")
