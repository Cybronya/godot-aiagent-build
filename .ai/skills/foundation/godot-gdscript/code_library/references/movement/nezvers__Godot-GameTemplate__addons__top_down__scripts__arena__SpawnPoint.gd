# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/arena/SpawnPoint.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
class_name SpawnPoint
extends Marker2D

const resource_path:String = "res://addons/top_down/resources/arena_resources/spawn_point_resource.tres"

@export var boss_position:bool

func _ready()->void:
	var _spawn_point_resource:SpawnPointResource = load(resource_path)
	if !boss_position:
		_spawn_point_resource.add_position(global_position)
	else:
		_spawn_point_resource.add_boss_position(global_position)
