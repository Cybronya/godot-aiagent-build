# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/vfx/TransitionColor.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends ColorRect

onready var anim_player = $AnimationPlayer

func fade_to_color():
	show()
	anim_player.play("to_color")
	yield(anim_player, "animation_finished")
	hide()

func fade_from_color():
	show()
	anim_player.play("to_transparent")
	yield(anim_player, "animation_finished")
	hide()
