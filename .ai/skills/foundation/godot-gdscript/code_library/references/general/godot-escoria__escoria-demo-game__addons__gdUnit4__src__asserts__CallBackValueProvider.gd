# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/asserts/CallBackValueProvider.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
# a value provider unsing a callback to get `next` value from a certain function
class_name CallBackValueProvider
extends ValueProvider

var _cb :Callable
var _args :Array


func _init(instance :Object, func_name :String, args :Array = Array(), force_error := true) -> void:
	_cb = Callable(instance, func_name);
	_args = args
	if force_error and not _cb.is_valid():
		push_error("Can't find function '%s' checked instance %s" % [func_name, instance])


func get_value() -> Variant:
	if not _cb.is_valid():
		return null
	if _args.is_empty():
		return await _cb.call()
	return await _cb.callv(_args)


func dispose() -> void:
	_cb = Callable()
