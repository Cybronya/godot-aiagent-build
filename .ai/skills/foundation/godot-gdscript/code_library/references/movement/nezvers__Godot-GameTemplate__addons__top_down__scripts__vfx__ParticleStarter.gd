# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/vfx/ParticleStarter.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
extends GPUParticles2D

func _ready()->void:
	set_emitting.call_deferred(true)
