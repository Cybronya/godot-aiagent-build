# Source:  https://github.com/MrEliptik/godot_experiments/blob/master/2D/juicy_bouncy_ball/bounce_particles.gd
# Repo:    MrEliptik/godot_experiments (star 1034) | License: MIT | Collected: 2026-10-29
# Commit:  4baec7290110
extends GPUParticles2D

func _ready():
	emitting = true
	$BounceParticles2.emitting = true
	await get_tree().create_timer($BounceParticles2.lifetime + 1.0).timeout
	queue_free()
	
