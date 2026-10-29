# Source:  https://github.com/foxssake/netfox/blob/main/examples/forest-brawl/scripts/effects/speed-effect.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends Effect

@export var bonus: float = 0.2

func _apply():
	get_target().speed *= 1 + bonus
	NetworkRollback.mutate(get_target())

func _cease():
	get_target().speed /= 1 + bonus
	NetworkRollback.mutate(get_target())
