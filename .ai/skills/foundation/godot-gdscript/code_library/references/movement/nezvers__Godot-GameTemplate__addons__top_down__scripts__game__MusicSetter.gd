# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/game/MusicSetter.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
class_name MusicSetter
extends Node

## Will call Music singleton to start music in it's dictionary
@export var music_name:String

func _ready()->void:
	Music.start(music_name)
