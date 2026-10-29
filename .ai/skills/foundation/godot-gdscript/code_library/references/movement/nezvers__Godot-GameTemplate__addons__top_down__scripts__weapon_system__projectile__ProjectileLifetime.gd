# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/weapon_system/projectile/ProjectileLifetime.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
class_name ProjectileLifetime
extends Node

@export var time:float = 1.0
@export var projectile:Projectile2D

var tween:Tween

func _ready()->void:
	if !(time > 0.0):
		return
	
	if tween != null:
		tween.kill()
	tween = create_tween()
	tween.tween_callback(_on_timeout).set_delay(time)

func _on_timeout()->void:
	projectile.prepare_exit()
