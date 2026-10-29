# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/actors/CoinsCollector.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Area2D

signal coins_received(amount)

const Coins = preload("res://core/inventory/items/Coins.gd")

func _on_area_entered(area):
	print(area)
	if not area is Coins:
		return
	area.queue_free()
	emit_signal("coins_received", area.amount)
