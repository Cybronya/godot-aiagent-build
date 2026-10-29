# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/actor/bots/TargetAim.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
class_name TargetAim
extends Node

@export var bot_input:BotInput
@export var target_finder:TargetFinder

## just point attack direction to the same direction as walking.
@export var aim_walking_direction:bool

func _ready()->void:
	target_finder.target_update.connect(_on_target_update)

func _on_target_update()->void:
	if aim_walking_direction:
		bot_input.input_resource.set_aim_direction((bot_input.input_resource.axis * bot_input.axis_compensation).normalized())
		return
	if target_finder.closest == null:
		return
	var direction:Vector2 = target_finder.closest.global_position - bot_input.global_position
	bot_input.input_resource.set_aim_direction((direction * bot_input.axis_compensation).normalized())
