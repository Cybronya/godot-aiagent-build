# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/finite_state_machine/player/bullet/bullet_spawner.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Node2D

var bullet := preload("Bullet.tscn")

func _unhandled_input(input_event: InputEvent) -> void:
	if input_event.is_action_pressed(&"fire"):
		fire()


func fire() -> void:
	if not $CooldownTimer.is_stopped():
		return

	$CooldownTimer.start()
	var new_bullet := bullet.instantiate()
	new_bullet.position = global_position
	new_bullet.direction = owner.look_direction
	add_child(new_bullet)
