# Source:  https://github.com/gaea-godot/gaea/blob/2.0/addons/gaea/runtime/graph_nodes/root/vector/constants/vector3i_constant.gd
# Repo:    gaea-godot/gaea (star 1663) | License: MIT | Collected: 2026-10-28
# Commit:  2.0
@tool
class_name GaeaNodeVector3iConstant
extends GaeaNodeConstant
## [Vector3i] constant.


func _get_output_port_type(_output_name: StringName) -> GaeaValue.Type:
	return GaeaValue.Type.VECTOR3I


func _get_title() -> String:
	return "Vector3iConstant"


func _get_description() -> String:
	return "[code]Vector3i[/code] constant."
