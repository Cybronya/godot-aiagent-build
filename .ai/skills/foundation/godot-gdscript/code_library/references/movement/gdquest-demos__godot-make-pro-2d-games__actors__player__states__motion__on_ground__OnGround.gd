# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/actors/player/states/motion/on_ground/OnGround.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends "../Motion.gd"

var speed = 0.0
var velocity = Vector2()

func handle_input(event):
	if event.is_action_pressed("jump"):
		emit_signal("finished", "jump")
	return .handle_input(event)
