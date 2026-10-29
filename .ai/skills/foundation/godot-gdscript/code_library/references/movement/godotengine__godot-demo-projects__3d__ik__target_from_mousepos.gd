# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/ik/target_from_mousepos.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Camera3D

@export var MOVEMENT_SPEED: float = 12
@export var flip_axis: bool = false

@onready var targets = $Targets


func _process(_delta):
	var mouse_to_world = (
			project_local_ray_normal(get_viewport().get_mouse_position()) * MOVEMENT_SPEED
		)

	if flip_axis:
		mouse_to_world = -mouse_to_world
	else:
		mouse_to_world.z *= -1

	targets.transform.origin = mouse_to_world
