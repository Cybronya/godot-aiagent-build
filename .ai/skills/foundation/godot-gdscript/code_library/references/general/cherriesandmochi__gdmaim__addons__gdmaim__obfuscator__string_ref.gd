# Source:  https://github.com/cherriesandmochi/gdmaim/blob/main/addons/gdmaim/obfuscator/string_ref.gd
# Repo:    cherriesandmochi/gdmaim (star 1327) | License: MIT | Collected: 2026-10-29
# Commit:  42a4eecf5418
extends RefCounted


const StringRef := preload("string_ref.gd")

var _value : String
var _root : WeakRef


func _init(value : String = "") -> void:
	_value = value


func _to_string() -> String:
	return _value if !_root else _root.get_ref()._to_string()


func set_value(value : String) -> void:
	_value = value


func get_value() -> String:
	return str(self)


func link(other : StringRef) -> void:
	_root = weakref(other)
