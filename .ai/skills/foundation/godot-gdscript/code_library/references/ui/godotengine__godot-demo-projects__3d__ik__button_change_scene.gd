# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/ik/button_change_scene.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Button

@export_file var scene_to_change_to: String = ""


func _ready():
	pressed.connect(change_scene)


func change_scene():
	if not scene_to_change_to.is_empty():
		get_tree().change_scene_to_file(scene_to_change_to)
