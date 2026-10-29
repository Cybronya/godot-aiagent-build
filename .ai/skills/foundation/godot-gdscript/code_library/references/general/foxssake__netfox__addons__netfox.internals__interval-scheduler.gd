# Source:  https://github.com/foxssake/netfox/blob/main/addons/netfox.internals/interval-scheduler.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends RefCounted
class_name _IntervalScheduler

# Returns true on every nth `is_now()` call

var interval := 1
var _idx := 0

func _init(p_interval: int = 1):
	interval = p_interval

func is_now() -> bool:
	if interval <= 0:
		return false
	elif interval == 1:
		return true
	elif _idx + 1 >= interval:
		_idx = 0
		return true
	else:
		_idx += 1
		return false
