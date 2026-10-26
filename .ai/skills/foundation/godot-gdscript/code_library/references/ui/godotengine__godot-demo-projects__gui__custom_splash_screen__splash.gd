# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/gui/custom_splash_screen/splash.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Control


func _on_animation_player_animation_finished(_anim_name: StringName) -> void:
	# Use `load()` instead of `preload()` to avoid delaying the splash screen's appearance.
	get_tree().change_scene_to_packed(load("res://main.tscn"))
