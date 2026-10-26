# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/finite_state_machine/player/player_controller.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends CharacterBody2D
# The Player is a CharacterBody2D, in other words a physics-driven object.
# It can move, collide with the world, etc...
# The player has a state machine, but the body and the state machine are separate.

signal direction_changed(new_direction: Vector2)

var look_direction := Vector2.RIGHT:
	set(value):
		look_direction = value
		set_look_direction(value)


func take_damage(attacker: Node, amount: float, effect: Node = null) -> void:
	if is_ancestor_of(attacker):
		return

	$States/Stagger.knockback_direction = (attacker.global_position - global_position).normalized()
	$Health.take_damage(amount, effect)


func set_dead(value: bool) -> void:
	set_process_input(not value)
	set_physics_process(not value)
	$CollisionPolygon2D.disabled = value


func set_look_direction(value: Vector2) -> void:
	direction_changed.emit(value)
