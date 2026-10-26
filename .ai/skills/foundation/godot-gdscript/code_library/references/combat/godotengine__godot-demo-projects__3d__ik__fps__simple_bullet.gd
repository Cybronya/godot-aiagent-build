# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/ik/fps/simple_bullet.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends RigidBody3D

const DESPAWN_TIME = 5

var timer = 0


func _ready():
	set_physics_process(true);


func _physics_process(delta):
	timer += delta
	if timer > DESPAWN_TIME:
		queue_free()
		timer = 0
