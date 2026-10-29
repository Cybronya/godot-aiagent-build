# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/finite_state_machine/player/states/combat/attack.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends "res://player/player_state.gd"

func enter() -> void:
	owner.get_node(^"AnimationPlayer").play(PLAYER_STATE.idle)


func _on_Sword_attack_finished() -> void:
	finished.emit(PLAYER_STATE.previous)
