# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/AI/Steering/Behaviors/Individual/SeekBehavior2D.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
extends SteeringBehavior2D
class_name SeekBehavior2D
# Constantly accelerates towards the target as fast as it can.


var target: Node2D


# Returns the steering motion filled with a linear acceleration amount that will make it go to where
# the target currently is, as fast as it is allowed by the controller.
func _calculate_steering_internal(steering: SteeringMotion2D) -> SteeringMotion2D:
	if not target:
		return steering.reset_values()

	steering.velocity = (target.position - get_actor().position).normalized() * controller.max_acceleration
	steering.angular_velocity = 0
	return steering
