# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/actors/player/states/motion/on_ground/BumpPlayer.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends "res://utils/state/State.gd"

export(float) var SPEED = 240.0
var direction = Vector2(-1.0, 0.0)

func _on_Move_last_moved(moved_direction):
	direction = -moved_direction

func enter():
	owner.get_node('AnimationPlayer').play('bump')

func update(delta):
	owner.move_and_slide(direction * SPEED)

func _on_animation_finished(anim_name):
	emit_signal('finished', 'idle')
