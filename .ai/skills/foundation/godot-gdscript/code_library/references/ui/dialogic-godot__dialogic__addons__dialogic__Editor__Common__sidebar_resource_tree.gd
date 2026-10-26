# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Editor/Common/sidebar_resource_tree.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  main
@tool
extends Tree

var previous_selected : TreeItem = null

func _get_drag_data(at_position: Vector2) -> Variant:
	var item := get_item_at_position(at_position)
	if item and item.get_metadata(0) and typeof(item.get_metadata(0)) == TYPE_STRING and item.get_metadata(0).begins_with("res://"):
		return {"files":[item.get_metadata(0)]}
	return null
