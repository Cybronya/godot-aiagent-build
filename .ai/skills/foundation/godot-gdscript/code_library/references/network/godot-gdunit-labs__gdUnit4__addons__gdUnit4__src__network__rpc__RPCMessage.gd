# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/network/rpc/RPCMessage.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name RPCMessage
extends RPC

var _message: String


static func of(msg: String) -> RPCMessage:
	var rpc := RPCMessage.new()
	rpc._message = msg
	return rpc


func message() -> String:
	return _message


func _to_string() -> String:
	return "RPCMessage: " + _message
