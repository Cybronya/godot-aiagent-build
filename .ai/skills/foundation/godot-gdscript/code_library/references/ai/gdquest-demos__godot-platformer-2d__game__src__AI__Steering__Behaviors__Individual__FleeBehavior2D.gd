# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/AI/Steering/Behaviors/Individual/FleeBehavior2D.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
extends SeekBehavior2D
class_name FleeBehavior2D
# FleeBehavior2D is the opposite of Seek. It constantly accelerates away from the target.

func _calculate_steering_internal(steering: SteeringMotion2D) -> SteeringMotion2D:
	._calculate_steering_internal(steering)
	steering.velocity *= -1
	return steering
