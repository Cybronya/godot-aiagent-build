# Source:  https://github.com/gaea-godot/gaea/blob/2.0/addons/gaea/runtime/graph_nodes/root/vector/constants/vector3_constant.gd
# Repo:    gaea-godot/gaea (star 1663) | License: MIT | Collected: 2026-10-28
# Commit:  2.0
@tool
class_name GaeaNodeVector3Constant
extends GaeaNodeConstant
## [Vector3] constant.


func _get_output_port_type(_output_name: StringName) -> GaeaValue.Type:
	return GaeaValue.Type.VECTOR3


func _get_title() -> String:
	return "Vector3Constant"


func _get_description() -> String:
	return "[code]Vector3[/code] constant."
