# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/physics_tests/utils/time_scale.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends HBoxContainer


func _on_h_slider_value_changed(value: float) -> void:
	value = maxf(0.1, value)
	$Value.text = "%.1f×" % value
	Engine.time_scale = value
	Engine.physics_ticks_per_second = $"../TicksPerSecond/HSlider".value * value
