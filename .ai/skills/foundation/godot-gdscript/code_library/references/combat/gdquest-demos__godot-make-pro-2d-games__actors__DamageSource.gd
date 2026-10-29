# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/actors/DamageSource.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Area2D

export(int) var damage = 2
var effect

func set_active(value):
	$CollisionShape2D.disabled = not value
