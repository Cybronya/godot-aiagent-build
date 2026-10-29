# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/misc/hdr_output/main/max_val_label.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Label


func _process(_delta: float) -> void:
	text = "%0.2f" % get_window().get_output_max_linear_value()
