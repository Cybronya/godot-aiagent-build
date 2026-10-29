# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/monitor/GdUnitMonitor.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
# GdUnit Monitoring Base Class
class_name GdUnitMonitor
extends RefCounted

var _id: String


# constructs new Monitor with given id
func _init(p_id: String) -> void:
	_id = p_id


# Returns the id of the monitor to uniqe identify
func id() -> String:
	return _id


# starts monitoring
func start() -> void:
	pass


# stops monitoring
func stop() -> void:
	pass
