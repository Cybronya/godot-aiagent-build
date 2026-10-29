# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/update/GdUnitPatch.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitPatch
extends RefCounted

const PATCH_VERSION = "patch_version"

var _version: GdUnit4Version


func _init(p_version: GdUnit4Version) -> void:
	_version = p_version


func version() -> GdUnit4Version:
	return _version


# this function needs to be implement
func execute() -> bool:
	push_error("The function 'execute()' is not implemented at %s" % self)
	return false
