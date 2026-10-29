# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/monsters/bosses/wild_boar/states/Spawn.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends "res://utils/state/State.gd"

func enter():
	owner.set_invincible(true)
	owner.get_node('AnimationPlayer').play('spawn')

func exit():
	owner.set_invincible(false)

func _on_animation_finished(anim_name):
	assert(anim_name == 'spawn')
	emit_signal('finished')
