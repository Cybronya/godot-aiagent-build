# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/great_games_library/resources/SoundResource/NestedSoundResource.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
extends SoundResource
class_name NestedSoundResource

@export var sound_resource_list:Array[SoundResource]
@export var random_order:bool

var index:int = 0

func play(_sound_player:SoundPlayer)->void:
	if random_order:
		sound_resource_list.pick_random().play(_sound_player)
	else:
		index = (index +1) % sound_resource_list.size()
		sound_resource_list[index].play(_sound_player)
