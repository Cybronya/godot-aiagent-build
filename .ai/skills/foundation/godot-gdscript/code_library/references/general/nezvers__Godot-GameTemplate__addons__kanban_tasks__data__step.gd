# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/kanban_tasks/data/step.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  master
@tool
extends "kanban_resource.gd"

## Data of a step.


var details: String:
	set(value):
		details = value
		__notify_changed()

var done: bool:
	set(value):
		done = value
		__notify_changed()


func _init(p_details: String = "", p_done: bool = false) -> void:
	details = p_details
	done = p_done
	super._init()


func to_json() -> Dictionary:
	return {
		"details": details,
		"done": done,
	}


func from_json(json: Dictionary) -> void:
	if json.has("details"):
		details = json["details"]
	else:
		push_warning("Loading incomplete json data which is missing details.")

	if json.has("done"):
		done = json["done"]
	else:
		push_warning("Loading incomplete json data which is missing 'done'.")
