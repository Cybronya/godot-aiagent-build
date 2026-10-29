# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/great_games_library/resources/SoundResource/ListSoundResource.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
extends SoundResource
class_name ListSoundResource

@export var sound_list:Array[AudioStream]
@export var random_order:bool

var index:int = 0

func get_sound()->AudioStream:
	if random_order:
		return sound_list[randi() % sound_list.size()]
	else:
		index = (index +1) % sound_list.size()
		return sound_list[index]
