# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/core/inventory/items/usable/potions/HealthPotion.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends "res://core/inventory/items/Item.gd"

export(int) var HEAL_AMOUNT = 20

func _apply_effect(user):
	if not user.has_node("Health"):
		return

	user.get_node("Health").heal(HEAL_AMOUNT)
	user.get_node("AnimationPlayer").play("heal")
