# Source:  https://github.com/foxssake/netfox/blob/main/examples/multiplayer-fps/scripts/ui/health-progress-bar.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends ProgressBar

@export var player: CharacterBody3D

func _process(delta: float):
	value = player.health
