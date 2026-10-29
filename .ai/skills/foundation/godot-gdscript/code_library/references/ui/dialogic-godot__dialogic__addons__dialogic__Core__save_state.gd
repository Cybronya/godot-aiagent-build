# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Core/save_state.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  701b67bbe601
class_name DialogicSaveState
extends Resource

@export var timeline := ""
@export var event_index := -1
@export var subsystems: Dictionary[String, Dictionary] = {}
