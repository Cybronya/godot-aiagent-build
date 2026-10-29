# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/great_games_library/static/VerletIntegration/VerletIntegration.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
## WARNING: Not implemented yet
class_name VerletIntegration
extends Node

## Forward And  Backwards Reach Inverse Kinematics
## Provide array with limb length and point array that holds position state (has to be one element bigger size)
static func rope_2d(length_list:PackedFloat32Array, point_list:PackedVector2Array, from:Vector2, to:Vector2, itterations:int = 10, error_margin:float = 0.1)->void:
	var joint_count: = length_list.size()
	# TODO: implement
