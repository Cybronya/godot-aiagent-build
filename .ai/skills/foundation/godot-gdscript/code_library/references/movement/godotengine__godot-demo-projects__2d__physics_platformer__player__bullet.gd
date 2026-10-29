# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/physics_platformer/player/bullet.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
class_name Bullet
extends RigidBody2D

var disabled: bool = false

func _ready() -> void:
	($Timer as Timer).start()


func disable() -> void:
	if disabled:
		return

	($AnimationPlayer as AnimationPlayer).play(&"shutdown")
	disabled = true
