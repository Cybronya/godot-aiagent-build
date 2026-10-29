# Source:  https://github.com/SirRamEsq/SmartShape2D/blob/master/addons/rmsmartshape/actions/action_make_shape_unique.gd
# Repo:    SirRamEsq/SmartShape2D (star 1761) | License: MIT | Collected: 2026-10-29
# Commit:  9617190250d0
extends SS2D_Action
class_name SS2D_ActionMakeShapeUnique

var _shape: SS2D_Shape
var _old_array: SS2D_Point_Array
var _new_array: SS2D_Point_Array


func _init(shape: SS2D_Shape) -> void:
	_shape = shape
	_old_array = shape.get_point_array()
	_new_array = _shape.get_point_array().clone(true)


func get_name() -> String:
	return "Make Shape Unique"


func do() -> void:
	_shape.set_point_array(_new_array)


func undo() -> void:
	_shape.set_point_array(_old_array)
