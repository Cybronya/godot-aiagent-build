# Source:  https://github.com/foxssake/netfox/blob/main/examples/forest-brawl/scripts/explosion.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends CPUParticles3D

func _ready():
	emitting = true
	one_shot = true

func _process(_delta):
	if not emitting:
		queue_free()
