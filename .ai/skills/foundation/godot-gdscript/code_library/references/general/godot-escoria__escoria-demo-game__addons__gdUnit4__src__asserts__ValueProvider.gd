# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/asserts/ValueProvider.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
# base interface for assert value provider
class_name ValueProvider
extends RefCounted

func get_value() -> Variant:
	return null


func dispose() -> void:
	pass
