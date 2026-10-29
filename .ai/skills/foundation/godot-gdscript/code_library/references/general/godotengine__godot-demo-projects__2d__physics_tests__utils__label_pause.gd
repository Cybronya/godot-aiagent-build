# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/physics_tests/utils/label_pause.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Label


func _process(_delta: float) -> void:
	visible = get_tree().paused
