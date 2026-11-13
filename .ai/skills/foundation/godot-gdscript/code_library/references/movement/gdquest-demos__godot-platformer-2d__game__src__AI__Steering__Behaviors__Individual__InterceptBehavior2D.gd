# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/AI/Steering/Behaviors/Individual/InterceptBehavior2D.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
extends SteeringBehavior2D
class_name InterceptBehavior2D
# Attempts to predict where the target is headed, and points its acceleration towards that point.

# # Properties:

# # - `max_prediction_time` is how far into the future in fixed time scale the AI will use to predict
# where the target is headed


export var max_prediction_time := 0.0

var target: Node2D


# Returns the steering motion filled with a linear acceleration amount that will send it on an
# intercept course with wherever the target is headed so that its arrival will cross with the
# target's.
func _calculate_steering_internal(steering: SteeringMotion2D) -> SteeringMotion2D:
	if not target:
		return steering.reset_values()

	var target_position := target.position
	var distance2 := (target_position - get_actor().position).length_squared()
	var speed2 := controller.velocity.length_squared()

	var prediction_time := max_prediction_time

	if speed2 > 0:
		var prediction_time2 = distance2 / speed2
		if prediction_time2 < max_prediction_time * max_prediction_time:
			prediction_time = sqrt(prediction_time2)

	steering.velocity = target_position + (controller.target_velocity * prediction_time)
	steering.velocity = (steering.velocity - get_actor().position).normalized() * controller.max_acceleration
	steering.angular_velocity = 0

	return steering
