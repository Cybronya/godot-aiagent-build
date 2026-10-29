# Source:  https://github.com/SirRamEsq/SmartShape2D/blob/master/addons/rmsmartshape/actions/action_delete_point.gd
# Repo:    SirRamEsq/SmartShape2D (star 1761) | License: MIT | Collected: 2026-10-29
# Commit:  9617190250d0
extends SS2D_ActionDeletePoints
class_name SS2D_ActionDeletePoint


func _init(shape: SS2D_Shape, key: int, commit_update: bool = true) -> void:
	var keys: PackedInt32Array = [key]
	super(shape, keys, commit_update)


func get_name() -> String:
	var pos := _shape.get_point_array().get_point_position(_keys[0])
	return "Delete Point at (%d, %d)" % [pos.x, pos.y]
