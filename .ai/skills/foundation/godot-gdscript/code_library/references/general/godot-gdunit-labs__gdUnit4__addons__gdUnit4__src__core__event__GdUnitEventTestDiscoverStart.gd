# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/core/event/GdUnitEventTestDiscoverStart.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitEventTestDiscoverStart
extends GdUnitEvent


func _init() -> void:
	_event_type = DISCOVER_START
