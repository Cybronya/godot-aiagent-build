# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/asserts/ValueProvider.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
# base interface for assert value provider
class_name ValueProvider
extends RefCounted


func get_value() -> Variant:
	return null


func dispose() -> void:
	pass
