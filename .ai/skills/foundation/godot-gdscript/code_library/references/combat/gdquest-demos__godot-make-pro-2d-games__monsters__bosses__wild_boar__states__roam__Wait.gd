# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/monsters/bosses/wild_boar/states/roam/Wait.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends "res://utils/state/State.gd"

func enter():
	owner.get_node('AnimationPlayer').play('idle')
	$Timer.start()

func update(delta):
	if $Timer.time_left <= 0.0:
		emit_signal('finished')

func exit():
	$Timer.stop()
