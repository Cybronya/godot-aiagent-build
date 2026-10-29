# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/vfx/particles/smoke/ParticlesPlayer.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Particles2D

func play():
	emitting = true
	for child in get_children():
		if not child.get_class() == "Particles2D":
			continue
		child.emitting = true
