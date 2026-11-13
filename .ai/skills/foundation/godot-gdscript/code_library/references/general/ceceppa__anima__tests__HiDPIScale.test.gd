# Source:  https://github.com/ceceppa/anima/blob/main/tests/HiDPIScale.test.gd
# Repo:    ceceppa/anima (star 769) | License: MIT | Collected: 2026-10-31
# Commit:  f4a454ebd4d5
extends "res://addons/gut/test.gd"

func test_apply_to_leaves_the_default_scale_on_a_normal_density_display():
	var control := Control.new()
	add_child_autofree(control)

	var before := control.get_window().content_scale_factor
	HiDPIScale.apply_to(control)

	assert_eq(control.get_window().content_scale_factor, before, "a normal-density display should not change the window's content scale")
