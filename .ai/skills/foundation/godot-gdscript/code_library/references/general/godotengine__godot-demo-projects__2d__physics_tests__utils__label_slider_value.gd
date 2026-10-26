# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/physics_tests/utils/label_slider_value.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
@tool
extends Label


func _process(_delta: float) -> void:
	var slider: HSlider = get_node(^"../HSlider")
	text = "%.1f" % slider.value
