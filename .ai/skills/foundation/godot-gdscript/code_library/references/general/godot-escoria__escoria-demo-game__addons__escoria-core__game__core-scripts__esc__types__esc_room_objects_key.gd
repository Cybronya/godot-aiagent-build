# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/escoria-core/game/core-scripts/esc/types/esc_room_objects_key.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
## Simple pair container to store a room's identifying information for use in
## the object manager.
class_name ESCRoomObjectsKey
extends RefCounted


## Contains the `global_id` of the room being represented by this key.
var room_global_id: String = ""

## Contains the instance ID of the room being represented by this key.
var room_instance_id: int = -1


## Checks whether this key is valid and represents an actual room.[br]
## [br]
## #### Parameters[br]
## [br]
## None.
## [br]
## #### Returns[br]
## [br]
## Returns a `bool` value. (`bool`)
func is_valid() -> bool:
	return not room_global_id.is_empty() and room_instance_id > -1
