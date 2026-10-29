# Source:  https://github.com/foxssake/netfox/blob/main/examples/shared/scripts/network-boostrapper.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends Node
class_name NetworkBootstrapper

static var _is_dedicated_host := false

static func is_dedicated_host() -> bool:
	return _is_dedicated_host

static func set_dedicated_host(p_is_dedicated_host: bool) -> void:
	_is_dedicated_host = p_is_dedicated_host
