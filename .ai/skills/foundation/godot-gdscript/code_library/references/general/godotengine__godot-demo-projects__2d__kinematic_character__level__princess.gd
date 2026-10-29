# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/kinematic_character/level/princess.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Node

func _on_body_entered(body: Node2D) -> void:
	if body.name == "Player":
		$"../WinText".show()
