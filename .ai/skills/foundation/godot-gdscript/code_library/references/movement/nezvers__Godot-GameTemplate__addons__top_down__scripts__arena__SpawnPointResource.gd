# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/arena/SpawnPointResource.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  master
class_name SpawnPointResource
extends SaveableResource

@export var position_list:Array[Vector2]

@export var boss_position_list:Array[Vector2]

func add_position(position:Vector2)->void:
	position_list.append(position)

func add_boss_position(position:Vector2)->void:
	boss_position_list.append(position)
