# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/asserts/DefaultValueProvider.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
# default value provider, simple returns the initial value
class_name DefaultValueProvider
extends ValueProvider

var _value: Variant


func _init(value: Variant) -> void:
	_value = value


func get_value() -> Variant:
	return _value
