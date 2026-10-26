# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/loading/scene_changer/scene_a.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Panel

func _on_goto_scene_pressed() -> void:
	# Change the scene to the one located at the given path.
	get_tree().change_scene_to_file("res://scene_b.tscn")
