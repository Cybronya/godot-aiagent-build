# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/vfx/particles/SelfDestructingParticles.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Particles2D

func start():
	emitting = true
	yield(get_tree().create_timer(lifetime * speed_scale * 1.2), "timeout")
	queue_free()
