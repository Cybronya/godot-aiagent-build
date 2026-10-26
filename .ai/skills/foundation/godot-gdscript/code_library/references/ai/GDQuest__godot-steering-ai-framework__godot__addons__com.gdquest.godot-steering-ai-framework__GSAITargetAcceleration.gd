# Source:  https://github.com/GDQuest/godot-steering-ai-framework/blob/master/godot/addons/com.gdquest.godot-steering-ai-framework/GSAITargetAcceleration.gd
# Repo:    GDQuest/godot-steering-ai-framework (star 1588) | License: MIT | Collected: 2026-10-26
# Commit:  master
# A desired linear and angular amount of acceleration requested by the steering
# system.
# @category - Base types
class_name GSAITargetAcceleration

# Linear acceleration
var linear := Vector3.ZERO
# Angular acceleration
var angular := 0.0


# Sets the linear and angular components to 0.
func set_zero() -> void:
	linear.x = 0.0
	linear.y = 0.0
	linear.z = 0.0
	angular = 0.0


# Adds `accel`'s components, multiplied by `scalar`, to this one.
func add_scaled_accel(accel: GSAITargetAcceleration, scalar: float) -> void:
	linear += accel.linear * scalar
	angular += accel.angular * scalar


# Returns the squared magnitude of the linear and angular components.
func get_magnitude_squared() -> float:
	return linear.length_squared() + angular * angular


# Returns the magnitude of the linear and angular components.
func get_magnitude() -> float:
	return sqrt(get_magnitude_squared())
