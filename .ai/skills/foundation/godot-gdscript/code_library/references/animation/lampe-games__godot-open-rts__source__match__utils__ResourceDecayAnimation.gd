# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/source/match/utils/ResourceDecayAnimation.gd
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
extends Node3D

@onready var _particles = find_child("GPUParticles3D")


func _ready():
	await get_tree().physics_frame  # wait one frame for transform to propagate
	_particles.finished.connect(queue_free)
	_particles.emitting = true
