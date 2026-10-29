# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/kanban_tasks/data/stage.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
@tool
extends "kanban_resource.gd"

## Data of a stage.


var title: String:
	set(value):
		title = value
		__notify_changed()

var tasks: Array[String] = []:
	get:
		# Pass by value to avoid appending without emitting `changed`.
		return tasks.duplicate()
	set(value):
		tasks = value
		__notify_changed()


func _init(p_title: String = "", p_tasks: Array[String] = []) -> void:
	title = p_title
	tasks = p_tasks
	super._init()


func to_json() -> Dictionary:
	return {
		"title": title,
		"tasks": tasks,
	}


func from_json(json: Dictionary) -> void:
	if json.has("title"):
		title = json["title"]
	else:
		push_warning("Loading incomplete json data which is missing a title.")

	if json.has("tasks"):
		# HACK: Workaround for casting to typed array.
		var s: Array[String] = []
		for i in json["tasks"]:
			s.append(i)

		tasks = s
	else:
		push_warning("Loading incomplete json data which is missing a list of tasks.")
