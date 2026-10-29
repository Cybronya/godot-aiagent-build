# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/source/match/units/actions/Moving.gd
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
extends "res://source/match/units/actions/Action.gd"

var _target_position = null

@onready var _unit = Utils.NodeEx.find_parent_with_group(self, "units")
@onready var _movement_trait = _unit.find_child("Movement")


static func is_applicable(unit):
	return unit.find_child("Movement") != null


func _init(target_position):
	_target_position = target_position


func _ready():
	_movement_trait.move(_target_position)
	_movement_trait.movement_finished.connect(_on_movement_finished)


func _exit_tree():
	if is_inside_tree():
		_movement_trait.stop()


func _on_movement_finished():
	queue_free()
