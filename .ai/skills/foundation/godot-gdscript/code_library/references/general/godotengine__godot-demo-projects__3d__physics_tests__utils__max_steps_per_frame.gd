# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/physics_tests/utils/max_steps_per_frame.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends HBoxContainer


func _on_h_slider_value_changed(value: float) -> void:
	$Value.text = str(roundi(value))
	Engine.max_physics_steps_per_frame = roundi(value)
