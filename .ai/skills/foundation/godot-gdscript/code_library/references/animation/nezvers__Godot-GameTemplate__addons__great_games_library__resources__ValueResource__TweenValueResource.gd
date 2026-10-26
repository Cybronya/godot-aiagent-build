# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/great_games_library/resources/ValueResource/TweenValueResource.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  master
class_name TweenValueResource
extends ValueResource

var value:Tween : set = set_value

func set_value(_value:Tween)->void:
	# TODO: interupt with validate or override (clamp)
	value = _value
	updated.emit()
