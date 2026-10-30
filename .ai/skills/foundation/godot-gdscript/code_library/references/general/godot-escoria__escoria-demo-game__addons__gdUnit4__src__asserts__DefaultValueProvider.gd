# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/asserts/DefaultValueProvider.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
# default value provider, simple returns the initial value
class_name DefaultValueProvider
extends ValueProvider

var _value: Variant


func _init(value: Variant) -> void:
	_value = value


func get_value() -> Variant:
	return _value
