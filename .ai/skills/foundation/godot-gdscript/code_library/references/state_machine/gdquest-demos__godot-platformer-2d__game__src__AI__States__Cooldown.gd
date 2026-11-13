# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/AI/States/Cooldown.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
extends State
# Waits for a given amount of time

export var cooldown_time := 1.5

func enter(msg: Dictionary = {}) -> void:
	yield(get_tree().create_timer(cooldown_time), "timeout")
	_state_machine.transition_to("Search")
