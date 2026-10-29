# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/great_games_library/resources/SoundResource/SoundEmitterNode.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
class_name SoundEmitterNode
extends Node

@export var sound:SoundResource
@export var enabled:bool = true
@export var debug:bool = false

func set_enabled(value:bool)->void:
	enabled = value

func play()->void:
	if sound == null:
		return
	if !enabled:
		return
	if debug:
		pass
	sound.play_managed()
