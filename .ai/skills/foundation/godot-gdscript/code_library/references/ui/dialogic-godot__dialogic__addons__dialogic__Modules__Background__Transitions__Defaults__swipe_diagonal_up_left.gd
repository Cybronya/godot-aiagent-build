# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Modules/Background/Transitions/Defaults/swipe_diagonal_up_left.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  main
extends "res://addons/dialogic/Modules/Background/Transitions/simple_swipe_transitions.gd"

func _fade() -> void:
	var shader := setup_swipe_shader()
	var texture: GradientTexture2D = shader.get_shader_parameter('wipe_texture')
	texture.fill_from = Vector2.DOWN
	texture.fill_to = Vector2.RIGHT
	tween_shader_progress()
