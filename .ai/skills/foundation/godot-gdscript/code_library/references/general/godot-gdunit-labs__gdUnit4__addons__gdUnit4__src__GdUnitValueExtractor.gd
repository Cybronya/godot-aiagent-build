# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/GdUnitValueExtractor.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitValueExtractor
extends RefCounted
## This is the base interface for value extraction


## Extracts a value by given implementation
func extract_value(value: Variant) -> Variant:
	push_error("Uninplemented func 'extract_value'")
	return value
