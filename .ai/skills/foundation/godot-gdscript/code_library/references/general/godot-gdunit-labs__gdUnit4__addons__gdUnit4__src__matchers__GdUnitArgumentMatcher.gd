# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/matchers/GdUnitArgumentMatcher.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitArgumentMatcher
extends RefCounted
## The base class of all argument matchers


@warning_ignore("unused_parameter")
func is_match(_value: Variant) -> bool:
	return true


func _to_string() -> String:
	assert(false, "`_to_string()` Is not implemented!")
	return ""
