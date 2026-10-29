# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/core/event/GdUnitEventStop.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitStop
extends GdUnitEvent


func _init() -> void:
	_event_type = STOP
