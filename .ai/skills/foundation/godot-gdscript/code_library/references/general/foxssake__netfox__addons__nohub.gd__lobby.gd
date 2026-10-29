# Source:  https://github.com/foxssake/netfox/blob/main/addons/nohub.gd/lobby.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends RefCounted
class_name NohubLobby

var id: String = ""
var is_visible: bool = true
var is_locked: bool = false
var data: Dictionary = {}

func _to_string() -> String:
	return "NohubLobby(id=%s, is_visible=%s, is_locked=%s, data=%s)" % [id, is_visible, is_locked, data]
