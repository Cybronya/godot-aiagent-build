# Source:  https://github.com/viniciusgerevini/godot-aseprite-wizard/blob/godot_4/addons/AsepriteWizard/interface/shared/animation_player_drop_button.gd
# Repo:    viniciusgerevini/godot-aseprite-wizard (star 1396) | License: MIT | Collected: 2026-10-29
# Commit:  18ebea9868ea
@tool
extends Button

signal node_dropped(node_path)

func _can_drop_data(_pos, data):
	if data.type == "nodes":
		var node = get_node(data.nodes[0])
		return node is AnimationPlayer
	return false


func _drop_data(_pos, data):
	var path = data.nodes[0]
	node_dropped.emit(path)
