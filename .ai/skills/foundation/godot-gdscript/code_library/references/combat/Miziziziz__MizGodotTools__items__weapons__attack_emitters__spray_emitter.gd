# Source:  https://github.com/Miziziziz/MizGodotTools/blob/main/items/weapons/attack_emitters/spray_emitter.gd
# Repo:    Miziziziz/MizGodotTools (star 987) | License: MIT | Collected: 2026-10-29
# Commit:  cb548f9035a3
extends AttackEmitter

## add random variance to an attack

@export var max_random_angle = 3.0

func do_attack():
	rotation_degrees = randf_range(-max_random_angle, max_random_angle)
	super()
