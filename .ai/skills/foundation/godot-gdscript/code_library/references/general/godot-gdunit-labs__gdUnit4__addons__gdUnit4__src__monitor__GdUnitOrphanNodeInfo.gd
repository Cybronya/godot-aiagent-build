# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/monitor/GdUnitOrphanNodeInfo.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitOrphanNodeInfo
extends RefCounted

var _id: int
var _type: String
var _stack_element: GdUnitStackTraceElement


func _init(id: int, type: String, stack_element: GdUnitStackTraceElement) -> void:
	_id = id
	_type = type
	_stack_element = stack_element
