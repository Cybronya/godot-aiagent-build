# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/viewport/3d_in_2d/robot_3d.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Node
## A simple script that rotates the model.

@onready var model: Node3D = $Model


func _process(delta: float) -> void:
	model.rotation.y += delta * 0.7
