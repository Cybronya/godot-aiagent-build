# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/cmd/CmdCommand.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name CmdCommand
extends RefCounted

var _name: String
var _arguments: PackedStringArray


func _init(p_name: String, p_arguments := []) -> void:
	_name = p_name
	_arguments = PackedStringArray(p_arguments)


func name() -> String:
	return _name


func arguments() -> PackedStringArray:
	return _arguments


func add_argument(arg: String) -> void:
	@warning_ignore("return_value_discarded")
	_arguments.append(arg)


func _to_string() -> String:
	return "%s:%s" % [_name, ", ".join(_arguments)]
