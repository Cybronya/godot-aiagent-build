# Source:  https://github.com/heroiclabs/nakama-godot/blob/master/addons/com.heroiclabs.nakama/utils/NakamaException.gd
# Repo:    heroiclabs/nakama-godot (star 783) | License: Apache-2.0 | Collected: 2026-10-31
# Commit:  6dc7b3951d98
extends RefCounted

## An exception generated during a request. [br]
## Usually contains at least an error message.
class_name NakamaException

var _status_code : int = -1
var status_code : int:
	set(v):
		pass
	get:
		return _status_code

var _grpc_status_code : int = -1
var grpc_status_code : int:
	set(v):
		pass
	get:
		return _grpc_status_code

var _message : String = ""
var message : String:
	set(v):
		pass
	get:
		return _message

var _cancelled : bool = false
var cancelled : bool:
	set(v):
		pass
	get:
		return _cancelled

func _init(p_message : String = "", p_status_code : int = -1, p_grpc_status_code : int = -1, p_cancelled : bool = false):
	_status_code = p_status_code
	_grpc_status_code = p_grpc_status_code
	_message = p_message
	_cancelled = p_cancelled

func _to_string() -> String:
	return "NakamaException(StatusCode={%s}, Message='{%s}', GrpcStatusCode={%s})" % [_status_code, _message, _grpc_status_code]
