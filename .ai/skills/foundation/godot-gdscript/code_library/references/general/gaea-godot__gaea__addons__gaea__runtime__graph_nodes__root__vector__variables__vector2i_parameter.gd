# Source:  https://github.com/gaea-godot/gaea/blob/2.0/addons/gaea/runtime/graph_nodes/root/vector/variables/vector2i_parameter.gd
# Repo:    gaea-godot/gaea (star 1663) | License: MIT | Collected: 2026-10-28
# Commit:  2.0
@tool
class_name GaeaNodeVector2iParameter
extends GaeaNodeParameter
## [Vector2i] parameter editable in the inspector.


func _get_variant_type() -> int:
	return TYPE_VECTOR2I


func _get_title() -> String:
	return "Vector2iParameter"


func _get_description() -> String:
	return "[code]Vector2i[/code] parameter editable in the inspector."
