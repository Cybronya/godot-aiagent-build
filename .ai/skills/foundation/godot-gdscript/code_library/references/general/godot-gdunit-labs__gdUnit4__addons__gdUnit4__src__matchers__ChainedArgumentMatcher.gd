# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/matchers/ChainedArgumentMatcher.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name ChainedArgumentMatcher
extends GdUnitArgumentMatcher

var _matchers: Array


func _init(matchers: Array) -> void:
	_matchers = matchers


func is_match(arguments: Variant) -> bool:
	var arg_array: Array = arguments
	if arg_array == null or arg_array.size() != _matchers.size():
		return false

	for index in arg_array.size():
		var arg: Variant = arg_array[index]
		var matcher: GdUnitArgumentMatcher = _matchers[index]

		if not matcher.is_match(arg):
			return false
	return true
