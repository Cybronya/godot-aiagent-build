# Source:  https://github.com/gaea-godot/gaea/blob/2.0/addons/gaea/runtime/graph_nodes/root/map/mappers/basic_mapper.gd
# Repo:    gaea-godot/gaea (star 1663) | License: MIT | Collected: 2026-10-28
# Commit:  79461f6491e7
@tool
class_name GaeaNodeBasicMapper
extends GaeaNodeMapper
## Maps all non-empty cells in [param reference] to [param material].


func _get_title() -> String:
	return "Mapper"


func _get_description() -> String:
	return "Maps all non-empty cells in [param reference] to [param material]."


func _passes_mapping(
	reference_sample: GaeaValue.Sample, cell: Vector3i, _args: Dictionary[StringName, Variant]
) -> bool:
	return reference_sample.has(cell)
