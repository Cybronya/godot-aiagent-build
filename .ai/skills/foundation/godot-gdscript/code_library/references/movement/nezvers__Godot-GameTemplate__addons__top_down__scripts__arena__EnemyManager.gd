# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/arena/EnemyManager.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  master
class_name EnemyManager
extends Node


@export var wave_queue:SpawnQueueResource

func _ready()->void:
	if wave_queue == null:
		return
	## BUG: Workaround for stupid bug. Arrays, dictionaries and resources reference from PackedScene
	wave_queue = wave_queue.duplicate()
	wave_queue.waves = wave_queue.waves.duplicate()
	
	for i:int in wave_queue.waves.size():
		wave_queue.waves[i] = wave_queue.waves[i].duplicate()
