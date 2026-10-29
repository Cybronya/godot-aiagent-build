# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/actors/hit_box/HitBox.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Area2D

const DamageSource = preload("res://actors/DamageSource.gd")

func _on_area_entered(area):
	if not area is DamageSource:
		return
	owner.take_damage_from(area)

func set_active(value):
	$CollisionShape2D.disabled = not value
