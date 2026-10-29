# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/vfx/particles/explosions/Explosion.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Particles2D

func _ready():
	get_tree().create_timer(lifetime).connect('timeout', self, 'stop_emitting')
	get_tree().create_timer(lifetime * 2.0).connect('timeout', self, 'queue_free')

func stop_emitting():
	emitting = false
