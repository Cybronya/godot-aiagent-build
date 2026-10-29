# Source:  https://github.com/foxssake/netfox/blob/main/test/netfox.internals/interval-scheduler.test.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends VestTest

func get_suite_name() -> String:
	return "IntervalScheduler"

func suite() -> void:
	test("should never schedule on zero interval", func():
		var interval := _IntervalScheduler.new(0)
		expect_false(interval.is_now())
		expect_false(interval.is_now())
		expect_false(interval.is_now())
	)

	test("should always schedule on one interval", func():
		var interval := _IntervalScheduler.new(1)
		expect_true(interval.is_now())
		expect_true(interval.is_now())
		expect_true(interval.is_now())
	)

	test("should schedule on interval", func():
		var interval := _IntervalScheduler.new(3)
		expect_false(interval.is_now())
		expect_false(interval.is_now())
		expect_true(interval.is_now())

		expect_false(interval.is_now())
		expect_false(interval.is_now())
		expect_true(interval.is_now())
	)
