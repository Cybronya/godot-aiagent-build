# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/monsters/bosses/wild_boar/states/charge/Prepare.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends "res://utils/state/State.gd"

func enter():
	owner.get_node('AnimationPlayer').play('prepare')

func _on_animation_finished(anim_name):
	emit_signal('finished')
