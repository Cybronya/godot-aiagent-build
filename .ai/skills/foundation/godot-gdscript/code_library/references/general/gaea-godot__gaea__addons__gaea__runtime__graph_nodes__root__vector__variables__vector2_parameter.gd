# Source:  https://github.com/gaea-godot/gaea/blob/2.0/addons/gaea/runtime/graph_nodes/root/vector/variables/vector2_parameter.gd
# Repo:    gaea-godot/gaea (star 1663) | License: MIT | Collected: 2026-10-28
# Commit:  79461f6491e7
@tool
class_name GaeaNodeVector2Parameter
extends GaeaNodeParameter
## [Vector2] parameter editable in the inspector.


func _get_variant_type() -> int:
	return TYPE_VECTOR2


func _get_title() -> String:
	return "Vector2Parameter"


func _get_description() -> String:
	return "[code]Vector2[/code] parameter editable in the inspector."
