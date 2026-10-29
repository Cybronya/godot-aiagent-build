# Source:  https://github.com/foxssake/netfox/blob/main/examples/property-configuration/scripts/base-subject.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends CharacterBody3D

func _get_synchronized_state_properties() -> Array[String]:
	return ["name"]
