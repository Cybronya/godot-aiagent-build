# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/kanban_tasks/view/filter.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
@tool
extends RefCounted

## A filter configuration for searching tasks.


var text: String
## Whether to search in descriptions.
var advanced: bool


func _init(p_text: String = "", p_advanced: bool = false) -> void:
	text = p_text
	advanced = p_advanced
