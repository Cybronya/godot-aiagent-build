# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/network/rpc/RPCClientDisconnect.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name RPCClientDisconnect
extends RPC

var _client_id: int


func with_id(id: int) -> RPCClientDisconnect:
	_client_id = id
	return self


func client_id() -> int:
	return _client_id
