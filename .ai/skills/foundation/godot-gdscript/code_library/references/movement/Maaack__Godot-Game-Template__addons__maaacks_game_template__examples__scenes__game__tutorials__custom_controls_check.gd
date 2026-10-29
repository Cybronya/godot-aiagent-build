# Source:  https://github.com/Maaack/Godot-Game-Template/blob/main/addons/maaacks_game_template/examples/scenes/game/tutorials/custom_controls_check.gd
# Repo:    Maaack/Godot-Game-Template (star 1709) | License: MIT | Collected: 2026-10-26
# Commit:  5cc611f7dfcd
extends Control

@export var custom_actions : Array[StringName] = [
	&"move_left",
	&"move_right",
	&"move_forward",
	&"move_backward",
	&"jump"
]

@export var default_action_container : Control

func _has_custom_actions() -> bool:
	for custom_action in custom_actions:
		if not InputMap.has_action(custom_action):
			return false
	return true

func _ready():
	if _has_custom_actions():
		visible = true
		default_action_container.visible = false
	else:
		visible = false
		default_action_container.visible = true
