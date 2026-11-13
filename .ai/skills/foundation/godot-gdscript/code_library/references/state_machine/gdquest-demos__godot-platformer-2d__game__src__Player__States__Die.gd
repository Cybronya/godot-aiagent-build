# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/Player/States/Die.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
extends State


var last_checkpoint: Area2D = null


func _on_Player_animation_finished(_anim_name: String) -> void:
	_state_machine.transition_to('Spawn', {last_checkpoint = last_checkpoint})


func enter(msg: Dictionary = {}) -> void:
	assert("last_checkpoint" in msg)
	last_checkpoint = msg.last_checkpoint
	owner.camera_rig.is_active = true
	owner.skin.play("die")
	owner.skin.connect("animation_finished", self, "_on_Player_animation_finished")


func exit() -> void:
	owner.skin.disconnect("animation_finished", self, "_on_Player_animation_finished")
