# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/actors/weapons/bullet/BulletSpawner.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Node2D

var bullet = preload("Bullet.tscn")

func _input(event):
	if event.is_action_pressed("fire"):
		fire(owner.look_direction)

func fire(direction):
	if not $CooldownTimer.is_stopped():
		return

	$CooldownTimer.start()
	var new_bullet = bullet.instance()
	new_bullet.direction = direction
	add_child(new_bullet)
