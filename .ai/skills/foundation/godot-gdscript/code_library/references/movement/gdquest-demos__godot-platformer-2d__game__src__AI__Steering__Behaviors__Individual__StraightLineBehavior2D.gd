# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/AI/Steering/Behaviors/Individual/StraightLineBehavior2D.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
extends SteeringBehavior2D
class_name StraightLineBehavior2D
# 2D Behavior that acts like Seek, but for a specific Vector2 position instead of an Object.

export var arrival_tolerance := 5.0

var target: Vector2

func _calculate_steering_internal(steering: SteeringMotion2D) -> SteeringMotion2D:
	var actor = get_actor()
	var to_target: Vector2 = target - actor.position
	var distance := to_target.length()

	if distance <= arrival_tolerance:
		steering.reset_values()
	else:
		steering.velocity = (target - get_actor().position).normalized() * controller.max_acceleration
		steering.angular_velocity = 0
	return steering
