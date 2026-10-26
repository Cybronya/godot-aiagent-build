# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/physics_tests/utils/ticks_per_second.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends HBoxContainer


func _on_h_slider_value_changed(value: float) -> void:
	$Value.text = str(roundi(value))
	Engine.physics_ticks_per_second = roundi(value * Engine.time_scale)
