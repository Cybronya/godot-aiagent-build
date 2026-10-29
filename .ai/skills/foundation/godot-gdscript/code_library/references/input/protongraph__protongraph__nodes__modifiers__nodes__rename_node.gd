# Source:  https://github.com/protongraph/protongraph/blob/main/nodes/modifiers/nodes/rename_node.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
extends ProtonNode


func _init() -> void:
	type_id = "rename_node"
	title = "Rename Node"
	category = "Modifiers/Nodes"
	description = "Renames a node."

	create_input("node", "Node", DataType.NODE_3D)
	create_input("name", "Name", DataType.STRING)
	create_output("out", "Renamed node", DataType.NODE_3D)

	enable_type_mirroring_on_slot("node", "out")


func _generate_outputs() -> void:
	var node: Node = get_input_single("node", null)
	var new_name: String = get_input_single("name", "")

	if node:
		node.name = new_name

	set_output("out", node)
