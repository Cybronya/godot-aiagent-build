# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/core/event/GdUnitSessionClose.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitSessionClose
extends GdUnitEvent


func _init() -> void:
	_event_type = SESSION_CLOSE
