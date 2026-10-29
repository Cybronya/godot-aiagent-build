# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/core/parse/GdClassDescriptor.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdClassDescriptor
extends RefCounted

var _name: String
var _is_inner_class: bool
var _functions: Array[GdFunctionDescriptor]


func _init(p_name: String, p_is_inner_class: bool, p_functions: Array[GdFunctionDescriptor]) -> void:
	_name = p_name
	_is_inner_class = p_is_inner_class
	_functions = p_functions


func name() -> String:
	return _name


func is_inner_class() -> bool:
	return _is_inner_class


func functions() -> Array[GdFunctionDescriptor]:
	return _functions
