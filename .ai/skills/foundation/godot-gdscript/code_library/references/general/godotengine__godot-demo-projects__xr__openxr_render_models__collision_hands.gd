# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/xr/openxr_render_models/collision_hands.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
class_name CollisionHands3D
extends AnimatableBody3D

func _ready():
	# Make sure these are set correctly.
	top_level = true
	sync_to_physics = false
	process_physics_priority = -90


func _physics_process(_delta):
	# Follow our parent node around.
	var dest_transform = get_parent().global_transform

	# We just apply rotation for this example.
	global_basis = dest_transform.basis

	# Attempt to move to where our tracked hand is.
	move_and_collide(dest_transform.origin - global_position)
