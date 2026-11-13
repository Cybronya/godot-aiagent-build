# Source:  https://github.com/ceceppa/anima/blob/main/tests/AnimaGroupDistribution.test.gd
# Repo:    ceceppa/anima (star 769) | License: MIT | Collected: 2026-10-31
# Commit:  f4a454ebd4d5
extends "res://addons/gut/test.gd"

func test_distribution_rejects_negative_timing_values():
	var distribution := AnimaGroupDistribution.new()
	distribution.stagger_interval = -0.1
	distribution.total_stagger_duration = -0.2
	var errors := distribution.validate()
	assert_has(errors, "stagger_interval must be zero or greater")
	assert_has(errors, "total_stagger_duration must be zero or greater")
