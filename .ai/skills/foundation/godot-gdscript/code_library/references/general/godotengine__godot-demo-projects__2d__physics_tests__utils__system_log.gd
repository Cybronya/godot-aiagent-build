# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/physics_tests/utils/system_log.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Node

enum LogType {
	LOG,
	ERROR,
}

signal entry_logged(message: String, type: LogType)

func print_log(message: String) -> void:
	print(message)
	entry_logged.emit(message, LogType.LOG)


func print_error(message: String) -> void:
	push_error(message)
	printerr(message)
	entry_logged.emit(message, LogType.ERROR)
