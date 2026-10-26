# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/arena/SpawnWaveList.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  master
class_name SpawnWaveList
extends Resource

@export var is_boss:bool

@export var count:int

@export var instance_list:Array[InstanceResource]
