# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/Player/States/HopOnEnemy.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
extends State
# Player state when grappling an enemy. Waits to let player aim/take stock, then jumps up.


export var hop_impulse := 500.0
export var wait_duration := 0.6


func enter(_msg: Dictionary = {}) -> void:
	owner.stats.set_invulnerable_for_seconds(wait_duration*3)
	
	var timer := get_tree().create_timer(wait_duration)
	yield(timer, "timeout")
	
	owner.emit_signal("hopped_off_entity")
	
	owner.state_machine.transition_to('Move/Air', {impulse = hop_impulse, velocity = Vector2.ZERO})
