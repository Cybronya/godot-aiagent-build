# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/network/rpc/RPCMessage.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
class_name RPCMessage
extends RPC

var _message: String


static func of(msg :String) -> RPCMessage:
	var rpc := RPCMessage.new()
	rpc._message = msg
	return rpc


func message() -> String:
	return _message


func _to_string() -> String:
	return "RPCMessage: " + _message
