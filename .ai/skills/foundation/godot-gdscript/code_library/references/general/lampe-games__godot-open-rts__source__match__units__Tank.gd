# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/source/match/units/Tank.gd
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
extends "res://source/match/units/Unit.gd"

const WaitingForTargets = preload("res://source/match/units/actions/WaitingForTargets.gd")


func _ready():
	await super()
	action_changed.connect(_on_action_changed)
	action = WaitingForTargets.new()


func _on_action_changed(new_action):
	if new_action == null:
		action = WaitingForTargets.new()
