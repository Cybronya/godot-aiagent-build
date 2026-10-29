# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/weapon_system/SpreadShot.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
class_name SpreadShot
extends Node

@export var projectile_spawner:ProjectileSpawner
@export_range(0.0, 180.0) var random_angle_offset:float

## Angles from weapon are duplicated and used as reference angles
var stored_projectile_angles:Array[float] = [0.0]


func _ready()->void:
	stored_projectile_angles = projectile_spawner.projectile_angles.duplicate()
	projectile_spawner.prepare_spawn.connect(on_prepare_spawn)

func on_prepare_spawn()->void:
	for i:int in stored_projectile_angles.size():
		var rand_angle:float = randf_range(-random_angle_offset, random_angle_offset)
		projectile_spawner.projectile_angles[i] = stored_projectile_angles[i] + rand_angle
