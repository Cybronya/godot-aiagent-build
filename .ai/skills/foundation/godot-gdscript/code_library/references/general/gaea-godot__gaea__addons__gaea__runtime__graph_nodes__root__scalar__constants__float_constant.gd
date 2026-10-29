# Source:  https://github.com/gaea-godot/gaea/blob/2.0/addons/gaea/runtime/graph_nodes/root/scalar/constants/float_constant.gd
# Repo:    gaea-godot/gaea (star 1663) | License: MIT | Collected: 2026-10-28
# Commit:  79461f6491e7
@tool
class_name GaeaNodeFloatConstant
extends GaeaNodeConstant
## [float] constant.


func _get_output_port_type(_output_name: StringName) -> GaeaValue.Type:
	return GaeaValue.Type.FLOAT


func _get_title() -> String:
	return "FloatConstant"


func _get_description() -> String:
	return "[code]float[/code] constant."
