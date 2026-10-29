# Source:  https://github.com/foxssake/netfox/blob/main/addons/trimsock.gd/id/incremental_id_generator.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends TrimsockIDGenerator
class_name IncrementalTrimsockIDGenerator


var _at := -1


func get_id() -> String:
	_at += 1
	return "%x" % _at
