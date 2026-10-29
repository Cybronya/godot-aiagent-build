# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/voxel/menu/options/options.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Control

var prev_menu: Control

func _on_Back_pressed() -> void:
	prev_menu.visible = true
	visible = false
