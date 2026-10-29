# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/mobile/android_iap/setup_instructions.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends VBoxContainer

func _on_continue_btn_pressed() -> void:
	get_tree().change_scene_to_file("res://store.tscn")
