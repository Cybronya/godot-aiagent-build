# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/matchers/EqualsArgumentMatcher.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name EqualsArgumentMatcher
extends GdUnitArgumentMatcher

var _current: Variant
var _auto_deep_check_mode: bool


func _init(current: Variant, auto_deep_check_mode := false) -> void:
	_current = current
	_auto_deep_check_mode = auto_deep_check_mode


func is_match(value: Variant) -> bool:
	var case_sensitive_check := true
	return GdObjects.equals(_current, value, case_sensitive_check, compare_mode(value))


func compare_mode(value: Variant) -> GdObjects.CompareMode:
	if _auto_deep_check_mode and is_instance_valid(value):
		# we do deep check on all InputEvent's
		return GdObjects.CompareMode.PARAMETER_DEEP_TEST if value is InputEvent else GdObjects.CompareMode.OBJECT_REFERENCE
	return GdObjects.CompareMode.OBJECT_REFERENCE
