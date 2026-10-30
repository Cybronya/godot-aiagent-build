# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/update/GdUnitPatch.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
class_name GdUnitPatch
extends RefCounted

const PATCH_VERSION = "patch_version"

var _version :GdUnit4Version


func _init(version_ :GdUnit4Version) -> void:
	_version = version_


func version() -> GdUnit4Version:
	return _version


# this function needs to be implement
func execute() -> bool:
	push_error("The function 'execute()' is not implemented at %s" % self)
	return false
