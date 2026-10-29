# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/great_games_library/resources/ValueResource/ValueResource.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
class_name ValueResource
extends SaveableResource

## Child classes should emit when changing value 
signal updated

## Solely created to remove unused warning
func _stupid_warnings()->void:
	updated.emit()
