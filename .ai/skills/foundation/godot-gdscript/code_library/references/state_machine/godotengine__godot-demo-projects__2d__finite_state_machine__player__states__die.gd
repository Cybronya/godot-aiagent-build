# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/finite_state_machine/player/states/die.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends "res://player/player_state.gd"

# Initialize the state. E.g. change the animation.
func enter() -> void:
	owner.set_dead(true)
	owner.get_node(^"AnimationPlayer").play(PLAYER_STATE.die)


func _on_animation_finished(_anim_name: String) -> void:
	finished.emit(PLAYER_STATE.dead)
