# Source:  https://github.com/OctoD/godot-gameplay-systems/blob/main/addons/godot_gameplay_systems/inventory_system/resources/drop_table.gd
# Repo:    OctoD/godot-gameplay-systems (star 746) | License: MIT | Collected: 2026-10-31
# Commit:  9349931cc7a5
class_name DropTable extends Resource

## Represents a drop table.
##
## It has several [DropGroup] pools. Each pool has a chance of dropping one [Item] based on it's [member DropGroup.drop_chance].

@export_category("Drop")
## An array of [DropGroup]. Each pool can drop one item.
@export var pools: Array[DropGroup] = []


## Drops an array of [Item]s. 
## [br]It accepts an optional argument [code]drop_modifier[/code] which increases (or decreases if negative) drop chances for each [DropGroup] pool.
## [br]The greater the modifier, the higher the chances to drop [Item]s from the pools.
func drop(drop_modifier: float = 0.0) -> Array[Item]:
	var out: Array[Item] = []
	
	for pool in pools:
		var maybe_item = pool.drop(drop_modifier)
		
		if maybe_item != null:
			out.append(maybe_item)
	
	return out

