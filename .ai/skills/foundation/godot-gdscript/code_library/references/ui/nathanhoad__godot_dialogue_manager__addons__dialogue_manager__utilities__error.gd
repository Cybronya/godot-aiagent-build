# Source:  https://github.com/nathanhoad/godot_dialogue_manager/blob/main/addons/dialogue_manager/utilities/error.gd
# Repo:    nathanhoad/godot_dialogue_manager (star 3946) | License: MIT | Collected: 2026-10-26
# Commit:  ebfc3f0cb6e1
class_name DMError extends RefCounted

var line_number: int
var column_number: int
var error: int


func _init(data: Dictionary) -> void:
	line_number = data.get("line_number", 0)
	column_number = data.get("column_number", 0)
	error = data.get("error", DMConstants.ERR_UNKNOWN_ERROR)
