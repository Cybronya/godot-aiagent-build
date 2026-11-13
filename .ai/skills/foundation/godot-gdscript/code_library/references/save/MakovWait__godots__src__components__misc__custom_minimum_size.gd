# Source:  https://github.com/MakovWait/godots/blob/main/src/components/misc/custom_minimum_size.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
class_name CustomMinimumSize
extends Node


@export var custom_minimum_size: Vector2:
	set(value):
		custom_minimum_size = value
		if not Engine.is_editor_hint():
			_apply()


func _ready() -> void:
	_apply()


func _apply() -> void:
	var target := get_parent() as Control
	if target == null:
		return
	target.custom_minimum_size = custom_minimum_size * Config.EDSCALE
