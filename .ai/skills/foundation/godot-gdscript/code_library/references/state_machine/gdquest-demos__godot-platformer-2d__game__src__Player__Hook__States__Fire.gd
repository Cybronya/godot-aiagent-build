# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/Player/Hook/States/Fire.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
extends State


func _on_Cooldown_timeout() -> void:
	_state_machine.transition_to("Aim")


func enter(_msg: Dictionary = {}) -> void:
	owner.is_aiming = false

	var target: HookTarget = owner.snap_detector.target
	if not target:
		var distance := min(owner._radius, owner.get_local_mouse_position().length())
		owner.arrow.hook_position = owner.global_position + owner.get_local_mouse_position().normalized() * distance / 2.0
		_state_machine.transition_to("Aim")
		return

	owner.arrow.hook_position = target.global_position
	target.hooked_from(owner.global_position)

	owner.cooldown.connect("timeout", self, "_on_Cooldown_timeout", [], CONNECT_ONESHOT)
	owner.cooldown.start()

	owner.emit_signal("hooked_onto_target", target.global_position)
