# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/loading/scene_changer/scene_b.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Panel

func _on_goto_scene_pressed() -> void:
	# Change the scene to the given PackedScene.
	# Though it usually takes more code, this can have advantages, such as letting you load the
	# scene in another thread, or use a scene that isn't saved to a file.
	var scene: PackedScene = load("res://scene_a.tscn")
	get_tree().change_scene_to_packed(scene)
