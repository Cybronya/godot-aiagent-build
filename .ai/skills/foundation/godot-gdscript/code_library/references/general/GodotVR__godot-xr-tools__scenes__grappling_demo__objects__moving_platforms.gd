# Source:  https://github.com/GodotVR/godot-xr-tools/blob/master/scenes/grappling_demo/objects/moving_platforms.gd
# Repo:    GodotVR/godot-xr-tools (star 740) | License: MIT | Collected: 2026-10-31
# Commit:  6c6189bdfcdf
extends Node3D

# Rotation rate
@export var rate : float = 10.0

# Called every frame. 'delta' is the elapsed time since the previous frame.
func _physics_process(delta):
	rotate_y(deg_to_rad(delta * rate))
