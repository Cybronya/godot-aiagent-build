# Source:  https://github.com/MrEliptik/godot_ui_components/blob/main/scenes/loading_fluid/scripts/loading_fluid.gd
# Repo:    MrEliptik/godot_ui_components (star 777) | License: MIT | Collected: 2026-10-31
# Commit:  22d235569061
extends Control


func _ready() -> void:
	pass # Replace with function body.

func _on_animation_player_animation_finished(anim_name: StringName) -> void:
	get_tree().quit()
