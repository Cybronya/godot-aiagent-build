# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/monsters/bosses/wild_boar/states/roam/RoamSequence.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends "res://utils/state/Sequence.gd"

var start_position = Vector2()

func enter():
	start_position = owner.global_position
	.enter()

func exit():
	.exit()

func update(delta):
	.update(delta)
