# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/AI/Steering/SteeringMotion2D.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
extends Reference
class_name SteeringMotion2D
# Data container for linear and angular steering velocities calculated by behaviors that extend SteeringBehavior2D.


var velocity := Vector2.ZERO
var angular_velocity := 0.0


func reset_values() -> void:
	velocity = Vector2.ZERO
	angular_velocity = 0.0


func is_zero() -> bool:
	return velocity == Vector2.ZERO and angular_velocity == 0.0
