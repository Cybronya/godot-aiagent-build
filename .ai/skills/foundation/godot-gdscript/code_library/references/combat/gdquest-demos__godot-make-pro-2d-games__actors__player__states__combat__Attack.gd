# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/actors/player/states/combat/Attack.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
"""
The stagger state end with the stagger animation from the AnimationPlayer
The animation only affects the Body Sprite"s modulate property so 
it could stack with other animations if we had two AnimationPlayer nodes
"""
extends "res://utils/state/State.gd"

func enter():
	owner.get_node("AnimationPlayer").play("idle")
	owner.weapon.attack()

func _on_Sword_combo_finished():
	emit_signal("finished", "previous")
