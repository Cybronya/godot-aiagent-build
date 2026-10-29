# Source:  https://github.com/viniciusgerevini/godot-aseprite-wizard/blob/godot_4/addons/AsepriteWizard/importers/helpers/file_system_helper.gd
# Repo:    viniciusgerevini/godot-aseprite-wizard (star 1396) | License: MIT | Collected: 2026-10-29
# Commit:  18ebea9868ea
@tool
extends Node

const WAIT_TIME_IN_SECONDS := 0.8
var _time_left := 0.0
var _scheduled := false

## Schedule a file system scan. This method works like a debouncer
## postponing the scan until no more calls are being made
func schedule_file_system_scan() -> void:
	_time_left = WAIT_TIME_IN_SECONDS
	_scheduled = true


func _process(delta: float) -> void:
	if _scheduled:
		if _time_left > 0.0:
			_time_left -= delta
		else:
			_scheduled = false
			if not EditorInterface.get_resource_filesystem().is_scanning():
				EditorInterface.get_resource_filesystem().scan.call_deferred()
