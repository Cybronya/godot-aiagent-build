# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/matchers/EqualsArgumentMatcher.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
class_name EqualsArgumentMatcher
extends GdUnitArgumentMatcher

var _current :Variant
var _auto_deep_check_mode :bool


func _init(current :Variant, auto_deep_check_mode := false) -> void:
	_current = current
	_auto_deep_check_mode = auto_deep_check_mode


func is_match(value :Variant) -> bool:
	var case_sensitive_check := true
	return GdObjects.equals(_current, value, case_sensitive_check, compare_mode(value))


func compare_mode(value :Variant) -> GdObjects.COMPARE_MODE:
	if _auto_deep_check_mode and is_instance_valid(value):
		# we do deep check on all InputEvent's
		return GdObjects.COMPARE_MODE.PARAMETER_DEEP_TEST if value is InputEvent else GdObjects.COMPARE_MODE.OBJECT_REFERENCE
	return GdObjects.COMPARE_MODE.OBJECT_REFERENCE
