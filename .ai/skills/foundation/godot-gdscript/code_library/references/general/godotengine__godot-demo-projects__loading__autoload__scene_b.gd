# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/loading/autoload/scene_b.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Panel

func _on_goto_scene_pressed() -> void:
	global.goto_scene("res://scene_a.tscn")
