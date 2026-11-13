# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/Player/Hook/States/Aim.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
extends State


func unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("aim"):
		owner.is_aiming = not owner.is_aiming
	elif event.is_action_pressed("hook"):
		_state_machine.transition_to("Fire")


func physics_process(_delta: float) -> void:
	var cast: Vector2 = owner.get_aim_direction() * owner._radius
	var angle := cast.angle()
	owner.ray_cast.cast_to = cast
	owner.arrow.rotation = angle
	owner.snap_detector.rotation = angle
	owner.ray_cast.force_raycast_update()
