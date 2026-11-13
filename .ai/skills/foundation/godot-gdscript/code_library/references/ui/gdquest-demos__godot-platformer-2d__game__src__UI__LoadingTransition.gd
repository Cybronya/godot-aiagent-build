# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/UI/LoadingTransition.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
extends ColorRect

signal faded_to_black

onready var animation_player: AnimationPlayer = $AnimationPlayer


func fade_to_black() -> void:
	animation_player.play("fade_in")
	animation_player.queue("fade_in_extras")
	animation_player.queue("loading")


func fade_back_in() -> void:
	animation_player.clear_queue()
	animation_player.play("fade_out")


func _on_AnimationPlayer_animation_changed(old_name: String, new_name: String) -> void:
	if old_name == "fade_in":
		emit_signal("faded_to_black")
