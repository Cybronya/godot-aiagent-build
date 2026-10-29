# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/source/match/units/Helicopter.gd
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
extends "res://source/match/units/Unit.gd"

const ROTOR_SPEED = 800.0  # degrees/s

const WaitingForTargets = preload("res://source/match/units/actions/WaitingForTargets.gd")


func _ready():
	await super()
	action_changed.connect(_on_action_changed)
	action = WaitingForTargets.new()


func _physics_process(delta):
	find_child("Rotor").rotation_degrees.y += ROTOR_SPEED * delta


func _on_action_changed(new_action):
	if new_action == null:
		action = WaitingForTargets.new()
