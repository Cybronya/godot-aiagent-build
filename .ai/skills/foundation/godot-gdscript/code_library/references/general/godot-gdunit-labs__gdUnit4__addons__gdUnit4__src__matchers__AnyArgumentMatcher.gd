# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/matchers/AnyArgumentMatcher.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name AnyArgumentMatcher
extends GdUnitArgumentMatcher


@warning_ignore("unused_parameter")
func is_match(_value: Variant) -> bool:
	return true


func _to_string() -> String:
	return "any()"
