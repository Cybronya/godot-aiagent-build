# Source:  https://github.com/Orama-Interactive/Pixelorama/blob/master/src/Tools/DesignTools/EllipseTool.gd
# Repo:    Orama-Interactive/Pixelorama (star 10855) | License: MIT | Collected: 2026-10-27
# Commit:  master
extends "res://src/Tools/BaseShapeDrawer.gd"


func _get_shape_points_filled(pos: Vector2i, shape_size: Vector2i) -> Array[Vector2i]:
	return DrawingAlgos.get_ellipse_points_filled(pos, shape_size, 1)


func _get_shape_points(pos: Vector2i, shape_size: Vector2i) -> Array[Vector2i]:
	return DrawingAlgos.get_ellipse_points(pos, shape_size)
