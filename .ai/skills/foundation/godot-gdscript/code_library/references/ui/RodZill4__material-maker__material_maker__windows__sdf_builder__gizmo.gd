# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/windows/sdf_builder/gizmo.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
@tool
extends Node3D


@export_enum("NONE", "SDF2D", "SDF3D") var mode : int = 1:
	get:
		return mode
	set(new_value):
		mode = new_value
		if is_inside_tree():
			match mode:
				0:
					$ArrowX.mode = 3
					$ArrowY.mode = 3
					$ArrowZ.mode = 3
				1:
					$ArrowX.mode = 1
					$ArrowY.mode = 1
					$ArrowZ.mode = 2
				2:
					$ArrowX.mode = 0
					$ArrowY.mode = 0
					$ArrowZ.mode = 0


signal translated(v)
signal rotated(v, a)


func _ready():
	mode = mode

func _on_Arrow_move(v):
	position += v
	emit_signal("translated", v)

func _on_Arrow_rotate(v, a):
	emit_signal("rotated", v, a)
