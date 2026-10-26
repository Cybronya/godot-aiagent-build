# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/physics_tests/utils/slider.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends HSlider


@export var snap_step := 1.0


func _process(_delta: float) -> void:
	if Input.is_key_pressed(KEY_SHIFT):
		step = 0.1
	else:
		step = snap_step
