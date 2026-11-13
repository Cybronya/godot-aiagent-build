# Source:  https://github.com/OctoD/godot-gameplay-systems/blob/main/addons/godot_gameplay_systems/inventory_system/nodes/drop_3d.gd
# Repo:    OctoD/godot-gameplay-systems (star 746) | License: MIT | Collected: 2026-10-31
# Commit:  9349931cc7a5
class_name Drop3D extends Node3D

## Is a drop zone in a 3D world


# Emitted when items are dropped in this node.
signal item_dropped(item: Item, node: Node3D)


func _ready() -> void:	
	add_to_group("ggs.drop-node")
