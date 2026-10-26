# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/weapon_system/projectile/HitLimit.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  master
class_name HitLimit
extends Node

@export var projectile:Projectile2D
@export var data_transmitter:DataChannelTransmitter

## Starting with negative has infinite count
@export var target_hit_limit:int = 1

var remaining_hits:int

func _ready()->void:
	if target_hit_limit < 1:
		return
	remaining_hits = target_hit_limit
	if !data_transmitter.success.is_connected(on_hit):
		data_transmitter.success.connect(on_hit)

func on_hit()->void:
	if remaining_hits < 1:
		return
	remaining_hits -= 1
	if remaining_hits != 0:
		return
	
	projectile.prepare_exit()
