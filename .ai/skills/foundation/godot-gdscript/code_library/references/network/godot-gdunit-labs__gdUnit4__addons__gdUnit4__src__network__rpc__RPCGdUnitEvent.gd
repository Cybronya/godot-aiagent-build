# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/network/rpc/RPCGdUnitEvent.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name RPCGdUnitEvent
extends RPC


static func of(p_event: GdUnitEvent) -> RPCGdUnitEvent:
	return RPCGdUnitEvent.new(p_event)


func event() -> GdUnitEvent:
	return GdUnitEvent.new().deserialize(_data)


func _to_string() -> String:
	return "RPCGdUnitEvent: " + str(_data)
