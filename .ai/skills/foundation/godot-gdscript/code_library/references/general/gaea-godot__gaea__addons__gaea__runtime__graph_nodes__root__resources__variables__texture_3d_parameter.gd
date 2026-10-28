# Source:  https://github.com/gaea-godot/gaea/blob/2.0/addons/gaea/runtime/graph_nodes/root/resources/variables/texture_3d_parameter.gd
# Repo:    gaea-godot/gaea (star 1663) | License: MIT | Collected: 2026-10-28
# Commit:  2.0
@tool
class_name GaeaNodeTexture3DParameter
extends GaeaNodeParameter
## [Texture3D] parameter editable in the inspector.


func _get_variant_type() -> int:
	return TYPE_OBJECT


func _get_property_hint() -> PropertyHint:
	return PROPERTY_HINT_RESOURCE_TYPE


func _get_property_hint_string() -> String:
	return "Texture3D"


func _get_title() -> String:
	return "Texture3DParameter"


func _get_description() -> String:
	return "Texture3D parameter editable in the inspector."
