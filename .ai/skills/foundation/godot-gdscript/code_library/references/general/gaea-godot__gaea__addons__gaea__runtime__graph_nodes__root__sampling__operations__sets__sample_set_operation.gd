# Source:  https://github.com/gaea-godot/gaea/blob/2.0/addons/gaea/runtime/graph_nodes/root/sampling/operations/sets/sample_set_operation.gd
# Repo:    gaea-godot/gaea (star 1663) | License: MIT | Collected: 2026-10-28
# Commit:  79461f6491e7
@tool
class_name GaeaNodeSampleSetOp
extends GaeaNodeSetOp
## Sample version of [GaeaNodeSetOp].


func _get_title() -> String:
	return "SampleSetOp"


func _get_output_port_type(_output_name: StringName) -> GaeaValue.Type:
	return GaeaValue.Type.SAMPLE
