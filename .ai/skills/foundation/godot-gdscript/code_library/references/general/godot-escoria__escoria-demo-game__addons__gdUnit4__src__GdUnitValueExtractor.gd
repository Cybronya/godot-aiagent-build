# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/GdUnitValueExtractor.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
## This is the base interface for value extraction
class_name GdUnitValueExtractor
extends RefCounted


## Extracts a value by given implementation
func extract_value(value :Variant) -> Variant:
	push_error("Uninplemented func 'extract_value'")
	return value
