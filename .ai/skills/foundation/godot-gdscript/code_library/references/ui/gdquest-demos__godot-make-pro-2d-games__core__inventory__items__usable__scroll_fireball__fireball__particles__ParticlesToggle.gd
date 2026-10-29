# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/core/inventory/items/usable/scroll_fireball/fireball/particles/ParticlesToggle.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
tool
extends Particles2D

export(bool) var active = true setget set_active

func set_active(value):
	active = value
	emitting = value
	for child in get_children():
		if not child.get_class() == "Particles2D":
			continue
		child.emitting = value
