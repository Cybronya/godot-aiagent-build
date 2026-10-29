# Source:  https://github.com/foxssake/netfox/blob/main/examples/forest-brawl/scripts/random-name-input.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends LineEdit

func _ready():
	text = NameProvider.name()
