# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/core/inventory/items/usable/scroll_fireball/FireballScroll.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends "res://core/inventory/items/Item.gd"

export(PackedScene) var Fireball

func _apply_effect(user):
	var fireball = Fireball.instance()
	user.add_child(fireball)
