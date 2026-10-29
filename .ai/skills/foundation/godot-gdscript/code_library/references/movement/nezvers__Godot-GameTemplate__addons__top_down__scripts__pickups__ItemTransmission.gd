# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/pickups/ItemTransmission.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
class_name ItemTransmission
extends TransmissionResource

@export var item_resource:ItemResource

## Should result with a state change
func process(resource_node:ResourceNode)->void:
	match item_resource.type:
		ItemResource.ItemType.WEAPON:
			_weapon(resource_node)

func _weapon(resource_node:ResourceNode)->void:
	var _weapon_inventory:ItemCollectionResource = resource_node.get_resource("weapons")
	if _weapon_inventory.list.size() >= _weapon_inventory.max_items:
		failed()
		return
	
	_weapon_inventory.append(item_resource)
	success()
