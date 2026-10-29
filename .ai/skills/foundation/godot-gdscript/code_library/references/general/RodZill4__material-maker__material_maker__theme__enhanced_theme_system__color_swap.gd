# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/theme/enhanced_theme_system/color_swap.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
class_name ColorSwap
extends Resource

@export var name : String = ""

## Original color to be replaced
@export var orig : Color = Color():
	set(val):
		orig = val
		emit_changed()

## Replacement color
@export var target : Color = Color():
	set(val):
		target = val
		emit_changed()


func _init(_orig : Color =Color(), _target : Color =Color()) -> void:
	orig = _orig
	target = _target
