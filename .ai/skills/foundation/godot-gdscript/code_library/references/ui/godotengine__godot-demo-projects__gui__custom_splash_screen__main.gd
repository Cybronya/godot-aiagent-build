# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/gui/custom_splash_screen/main.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Control


func _on_restart_pressed() -> void:
	OS.set_restart_on_exit(true)
	get_tree().quit()
