# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/gdUnit4/src/network/rpc/RPCClientDisconnect.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
class_name RPCClientDisconnect
extends RPC

var _client_id: int


func with_id(id: int) -> RPCClientDisconnect:
	_client_id = id
	return self


func client_id() -> int:
	return _client_id
