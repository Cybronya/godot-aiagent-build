# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/lights_and_shadows/spin.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Node3D

var increment := 0.0

func _process(delta: float) -> void:
	position.x = sin(increment)
	position.z = cos(increment)
	# Avoid precision issues over time by rolling over every full turn.
	rotation.y = fmod(increment, TAU)

	increment += delta
