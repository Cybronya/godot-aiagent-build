# Source:  https://github.com/MrEliptik/godot_ui_components/blob/main/scenes/loading_animation/scripts/loading_animation.gd
# Repo:    MrEliptik/godot_ui_components (star 777) | License: MIT | Collected: 2026-10-31
# Commit:  22d235569061
extends Control


func _on_animation_player_animation_finished(anim_name):
	if anim_name == "rotate":
		get_tree().quit()
