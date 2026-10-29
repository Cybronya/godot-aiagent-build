# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/core/shop/purse/Purse.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Node

signal coins_changed(coins)

export(int) var coins = 0
export(int) var MAXIMUM = 1000000

func has_coins(amount):
	return coins >= amount

func add_coins(amount):
	coins = min(coins + amount, MAXIMUM)
	emit_signal("coins_changed", coins)

func remove_coins(amount):
	if not has_coins(amount):
		return
	coins = max(0, coins - amount)
	emit_signal("coins_changed", coins)
