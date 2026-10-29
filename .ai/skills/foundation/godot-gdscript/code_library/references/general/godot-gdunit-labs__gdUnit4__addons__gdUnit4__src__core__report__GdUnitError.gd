# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/core/report/GdUnitError.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitError
extends RefCounted

var _message: String
var _line_number: int
var _stack_trace: GdUnitStackTrace


func _init(message: String, line_number: int, stack_trace: GdUnitStackTrace) -> void:
	_message = message
	_line_number = line_number
	_stack_trace = stack_trace
