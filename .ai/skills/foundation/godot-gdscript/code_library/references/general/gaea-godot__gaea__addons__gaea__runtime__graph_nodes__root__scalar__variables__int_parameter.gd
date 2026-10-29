# Source:  https://github.com/gaea-godot/gaea/blob/2.0/addons/gaea/runtime/graph_nodes/root/scalar/variables/int_parameter.gd
# Repo:    gaea-godot/gaea (star 1663) | License: MIT | Collected: 2026-10-28
# Commit:  79461f6491e7
@tool
class_name GaeaNodeIntParameter
extends GaeaNodeParameter
## [int] parameter editable in the inspector.


func _get_variant_type() -> int:
	return TYPE_INT


func _get_title() -> String:
	return "IntParameter"


func _get_description() -> String:
	return "[code]int[/code] parameter editable in the inspector."
