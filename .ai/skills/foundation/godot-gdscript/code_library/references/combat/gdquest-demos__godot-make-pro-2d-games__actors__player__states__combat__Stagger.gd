# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/actors/player/states/combat/Stagger.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
"""
The stagger state end with the stagger animation from the AnimationPlayer
The animation only affects the Body Sprite"s modulate property so 
it could stack with other animations if we had two AnimationPlayer nodes
"""
extends "res://utils/state/State.gd"

var knockback_direction = Vector2()

func enter():
	owner.get_node("AnimationPlayer").play("stagger")

func _on_animation_finished(anim_name):
	owner.get_body().modulate = Color('#ffffff')
	emit_signal("finished", "previous")
