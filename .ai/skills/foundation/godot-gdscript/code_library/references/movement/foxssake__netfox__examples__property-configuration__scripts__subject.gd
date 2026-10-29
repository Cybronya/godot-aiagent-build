# Source:  https://github.com/foxssake/netfox/blob/main/examples/property-configuration/scripts/subject.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
@tool
extends "res://examples/property-configuration/scripts/base-subject.gd"

var health := 100
var movement := Vector2.ZERO

# These properties will be picked up by StateSynchronizer
func _get_synchronized_state_properties() -> Array:
	# Inheritance is also possible this way
	return super() + ["health"]

# These properties will be picked up by TickInterpolator
func _get_interpolated_properties() -> Array:
	return ["transform"]

# These properties will be picked up by RollbackSyncrhonizer as state
func _get_rollback_state_properties() -> Array:
	return ["transform"]
