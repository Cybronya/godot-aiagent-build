# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/dodge_the_creeps/mob.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends RigidBody2D

func _ready():
	var mob_types = Array($AnimatedSprite2D.sprite_frames.get_animation_names())
	$AnimatedSprite2D.animation = mob_types.pick_random()
	$AnimatedSprite2D.play()


func _on_VisibilityNotifier2D_screen_exited():
	queue_free()
