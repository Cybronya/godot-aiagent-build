# Source:  https://github.com/foxssake/netfox/blob/main/script_templates/VestTest/define.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
# meta-name: Test suite with define()
# meta-description: Test suite with a name set and test suite definition

extends _BASE_

func get_suite_name() -> String:
	return "_CLASS_"

func suite():
	# Add your test cases here
	test("some test", func():
		ok()
	)
	test("another test", func():
		todo("Implement tests")
	)
