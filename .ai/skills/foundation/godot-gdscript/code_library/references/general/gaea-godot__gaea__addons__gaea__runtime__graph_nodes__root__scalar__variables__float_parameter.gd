# Source:  https://github.com/gaea-godot/gaea/blob/2.0/addons/gaea/runtime/graph_nodes/root/scalar/variables/float_parameter.gd
# Repo:    gaea-godot/gaea (star 1663) | License: MIT | Collected: 2026-10-28
# Commit:  2.0
@tool
class_name GaeaNodeFloatParameter
extends GaeaNodeParameter
## [float] parameter editable in the inspector.


func _get_variant_type() -> int:
	return TYPE_FLOAT


func _get_title() -> String:
	return "FloatParameter"


func _get_description() -> String:
	return "[code]float[/code] parameter editable in the inspector."
