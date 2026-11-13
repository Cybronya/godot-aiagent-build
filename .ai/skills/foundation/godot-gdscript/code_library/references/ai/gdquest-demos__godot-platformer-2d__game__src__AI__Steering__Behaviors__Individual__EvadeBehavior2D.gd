# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/AI/Steering/Behaviors/Individual/EvadeBehavior2D.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
extends InterceptBehavior2D
class_name EvadeBehavior2D
# EvadeBehavior2D is the opposite of Intercept. It moves away from the target's projected position.
# See `InterceptBehavior2D` for more information.

# 
# Returns a steering motion filled with a linear acceleration amount that will move it away from the
# point where the target will be in `max_prediction_time`.
func _calculate_steering_internal(steering: SteeringMotion2D) -> SteeringMotion2D:
	._calculate_steering_internal(steering)
	steering.velocity *= -1
	return steering
