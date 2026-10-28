# Source:  https://github.com/gaea-godot/gaea/blob/2.0/addons/gaea/runtime/graph_nodes/root/scalar/constants/int_constant.gd
# Repo:    gaea-godot/gaea (star 1663) | License: MIT | Collected: 2026-10-28
# Commit:  2.0
@tool
class_name GaeaNodeIntConstant
extends GaeaNodeConstant
## [int] constant.


func _get_output_port_type(_output_name: StringName) -> GaeaValue.Type:
	return GaeaValue.Type.INT


func _get_title() -> String:
	return "IntConstant"


func _get_description() -> String:
	return "[code]int[/code] constant."
