# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/core/inventory/ItemDatabase.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Node

func get_item(reference):
	for item in get_children():
		if reference.name == item.name:
			return item.duplicate()

func get_items():
	return get_children()
