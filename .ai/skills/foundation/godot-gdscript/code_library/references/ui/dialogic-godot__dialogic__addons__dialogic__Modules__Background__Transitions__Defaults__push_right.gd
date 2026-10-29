# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Modules/Background/Transitions/Defaults/push_right.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  701b67bbe601
extends "res://addons/dialogic/Modules/Background/Transitions/simple_push_transitions.gd"

func _fade() -> void:
	var shader := setup_push_shader()
	shader.set_shader_parameter('final_offset', Vector2.RIGHT)
	tween_shader_progress().set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)

