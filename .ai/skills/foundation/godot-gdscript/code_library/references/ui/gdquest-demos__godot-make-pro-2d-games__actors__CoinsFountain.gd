# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/actors/CoinsFountain.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Position2D

const Coins = preload("res://core/inventory/items/Coins.tscn")

onready var timer = $Timer

export(int) var MAX_SPAWN_COUNT = 12
var spawn_cycles = 0

func start():
	timer.start()

func _on_Timer_timeout():
	spawn_random_coin_stack()

func spawn_random_coin_stack():
	var coins = Coins.instance()
	add_child(coins)
	coins.set_random_amount()
	coins.throw()
	spawn_cycles += 1
	if spawn_cycles == MAX_SPAWN_COUNT:
		timer.stop()
