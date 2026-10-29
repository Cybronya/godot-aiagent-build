# Source:  https://github.com/viniciusgerevini/godot-aseprite-wizard/blob/godot_4/addons/AsepriteWizard/config/logger.gd
# Repo:    viniciusgerevini/godot-aseprite-wizard (star 1396) | License: MIT | Collected: 2026-10-29
# Commit:  18ebea9868ea
@tool
extends RefCounted

const LOG_PREFIX = "[Aseprite Wizard] "

static func info(message: String, file_name: String = "") -> void:
	print(_build_log_line(message, file_name))


static func error(message: String, file_name: String = "") -> void:
	printerr(_build_log_line(message, file_name))


static func warn(message: String, file_name: String = "") -> void:
	print(_build_log_line("WARN: "+ message, file_name))


static func _build_log_line(message: String, file_name: String) -> String:
	if file_name == "":
		return LOG_PREFIX + message
	return "%s%s (%s)" % [LOG_PREFIX, message, file_name]
