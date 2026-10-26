# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/misc/hdr_output/output_max_linear_value/rotate.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Node3D

@export var rotation_speed: float = 1.0


func _process(delta: float) -> void:
	rotate_y(delta * rotation_speed)
