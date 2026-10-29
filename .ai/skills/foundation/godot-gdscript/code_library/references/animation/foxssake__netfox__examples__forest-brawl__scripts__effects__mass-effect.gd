# Source:  https://github.com/foxssake/netfox/blob/main/examples/forest-brawl/scripts/effects/mass-effect.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends Effect

@export var bonus_mass: float = 1.0

func _apply():
	get_target().mass += bonus_mass
	NetworkRollback.mutate(get_target())

func _cease():
	get_target().mass -= bonus_mass
	NetworkRollback.mutate(get_target())
