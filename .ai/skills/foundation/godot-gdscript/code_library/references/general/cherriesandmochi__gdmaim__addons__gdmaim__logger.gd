# Source:  https://github.com/cherriesandmochi/gdmaim/blob/main/addons/gdmaim/logger.gd
# Repo:    cherriesandmochi/gdmaim (star 1327) | License: MIT | Collected: 2026-10-29
# Commit:  42a4eecf5418
@tool
extends RefCounted


static var current_log : Variant
static var logs : Dictionary = {}


static func clear_all() -> void:
	logs.clear()


static func swap(new_log : Variant) -> void:
	current_log = new_log
	logs[new_log] = logs.get(new_log, "")


static func clear() -> void:
	logs[current_log] = ""


static func write(new_text : String) -> void:
	logs[current_log] += new_text + "\n"


static func get_log(target : Variant) -> String:
	return logs[target].trim_suffix("\n")


static func get_current() -> String:
	return logs[current_log].trim_suffix("\n")
