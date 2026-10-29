# Source:  https://github.com/foxssake/netfox/blob/main/script_templates/VestTest/test_methods.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
# meta-name: Test suite with methods
# meta-description: Test suite with a name set and test methods

extends _BASE_

func get_suite_name() -> String:
	return "_CLASS_"

# Add your test cases here
func test_case_a():
	ok()

func test_case_b():
	todo("Implement tests")
