# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/great_games_library/nodes/AnimationHelper/AnimationHelper.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
class_name AnimationHelper
extends Node

@export var animation_player:AnimationPlayer

## Allows for AnimationPlayers to call next animation
func play(animation:StringName, reset:bool = false)->void:
	assert(animation_player != null)
	if reset:
		animation_player.stop()
	animation_player.play(animation)
