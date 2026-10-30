# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/network/rpc/RPCGdUnitEvent.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
class_name RPCGdUnitEvent
extends RPC


static func of(p_event: GdUnitEvent) -> RPCGdUnitEvent:
	return RPCGdUnitEvent.new(p_event)


func event() -> GdUnitEvent:
	return GdUnitEvent.new().deserialize(_data)


func _to_string() -> String:
	return "RPCGdUnitEvent: " + str(_data)
