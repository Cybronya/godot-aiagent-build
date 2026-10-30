# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/matchers/GdUnitArgumentMatcher.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
## The base class of all argument matchers
class_name GdUnitArgumentMatcher
extends RefCounted


@warning_ignore("unused_parameter")
func is_match(value: Variant) -> bool:
	return true


func _to_string() -> String:
	assert(false, "`_to_string()` Is not implemented!")
	return ""
