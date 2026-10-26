# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/sprites/scripts/sprite_rotate.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Sprite3D

@export var speed_deg: float = 90.0


func _process(delta: float) -> void:
	rotate_y(deg_to_rad(speed_deg * delta))
