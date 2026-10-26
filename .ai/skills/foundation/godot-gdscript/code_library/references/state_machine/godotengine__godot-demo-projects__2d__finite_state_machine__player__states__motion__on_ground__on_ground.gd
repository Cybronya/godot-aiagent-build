# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/finite_state_machine/player/states/motion/on_ground/on_ground.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends "../motion.gd"

var speed := 0.0
var velocity := Vector2()

func handle_input(input_event: InputEvent) -> void:
	if input_event.is_action_pressed(&"jump"):
		finished.emit(PLAYER_STATE.jump)

	return super.handle_input(input_event)
