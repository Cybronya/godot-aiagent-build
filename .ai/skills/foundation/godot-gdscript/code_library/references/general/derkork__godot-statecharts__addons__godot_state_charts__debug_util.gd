# Source:  https://github.com/derkork/godot-statecharts/blob/main/addons/godot_state_charts/debug_util.gd
# Repo:    derkork/godot-statecharts (star 1623) | License: MIT | Collected: 2026-10-26
# Commit:  76d226a3efac
﻿## Returns the path of a node in the scene tree
## Returns the name of the node if the node is not in the tree.
static func path_of(node: Node) -> String:
	if node == null:
		return ""
	if !node.is_inside_tree():
		return node.name + " (not in tree)"
	return str(node.get_path())
