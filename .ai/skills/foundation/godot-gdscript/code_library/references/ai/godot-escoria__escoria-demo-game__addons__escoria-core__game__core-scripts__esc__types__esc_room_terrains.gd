# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/escoria-core/game/core-scripts/esc/types/esc_room_terrains.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
## Container for `NavigationPolygon`s stored in the object manager.
class_name ESCRoomTerrains
extends ESCRoomContainer


## The hash of terrains registered to the room.
var terrains: Dictionary = {}
