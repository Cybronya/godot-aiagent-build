# Source:  https://github.com/gaea-godot/gaea/blob/2.0/addons/gaea/runtime/graph_nodes/root/map/filters/random_filter.gd
# Repo:    gaea-godot/gaea (star 1663) | License: MIT | Collected: 2026-10-28
# Commit:  2.0
@tool
class_name GaeaNodeMapRandomFilter
extends GaeaNodeRandomFilter
## Map version of [GaeaNodeRandomFilter].


func _get_description() -> String:
	return super().replace("sample", "map")


func _get_output_port_type(_output_name: StringName) -> GaeaValue.Type:
	return GaeaValue.Type.MAP
