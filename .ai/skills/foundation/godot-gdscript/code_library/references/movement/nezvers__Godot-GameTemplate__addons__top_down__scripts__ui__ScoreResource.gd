# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/ui/ScoreResource.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
class_name ScoreResource
extends SaveableResource

signal updated

@export var value:int = 0

func reset_resource()->void:
	value = 0

func add_point()->void:
	value += 1
	updated.emit()
