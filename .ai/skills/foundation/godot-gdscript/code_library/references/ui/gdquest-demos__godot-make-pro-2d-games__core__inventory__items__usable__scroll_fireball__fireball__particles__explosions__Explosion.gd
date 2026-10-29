# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/core/inventory/items/usable/scroll_fireball/fireball/particles/explosions/Explosion.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Particles2D

func _ready():
	one_shot = true
	$SmallSparkles.one_shot = true
	get_tree().create_timer(lifetime * 2.0).connect('timeout', self, 'queue_free')
