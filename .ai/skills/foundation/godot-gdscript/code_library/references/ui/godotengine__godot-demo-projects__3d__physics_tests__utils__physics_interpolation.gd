# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/physics_tests/utils/physics_interpolation.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends CheckButton


func _on_check_button_toggled(toggled_on: bool) -> void:
	get_tree().physics_interpolation = toggled_on
