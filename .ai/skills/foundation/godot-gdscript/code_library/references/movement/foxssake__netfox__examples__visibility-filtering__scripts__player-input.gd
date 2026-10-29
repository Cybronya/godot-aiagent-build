# Source:  https://github.com/foxssake/netfox/blob/main/examples/visibility-filtering/scripts/player-input.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
@tool
extends BaseNetInput

var movement: Vector3
var is_jumping: bool

func _get_rollback_input_properties() -> Array:
	return [
		"movement",
		"is_jumping"
	]

func _gather():
	movement = Vector3(
		Input.get_axis("move_west", "move_east"),
		0.0,
		Input.get_axis("move_north", "move_south")
	)

	is_jumping = Input.is_action_pressed("move_jump")
