# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/core/event/GdUnitEventTestDiscoverEnd.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitEventTestDiscoverEnd
extends GdUnitEvent

var _total_testsuites: int


func _init(testsuite_count: int, test_count: int) -> void:
	_event_type = DISCOVER_END
	_total_testsuites = testsuite_count
	_total_count = test_count


func total_test_suites() -> int:
	return _total_testsuites


func total_tests() -> int:
	return _total_count
