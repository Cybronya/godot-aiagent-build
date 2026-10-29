# Source:  https://github.com/foxssake/netfox/blob/main/script_templates/VestTest/empty.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
# meta-name: Empty test suite
# meta-description: Test suite with a name set and no test methods or definitions
# meta-default: true

extends _BASE_

func get_suite_name() -> String:
	return "_CLASS_"
