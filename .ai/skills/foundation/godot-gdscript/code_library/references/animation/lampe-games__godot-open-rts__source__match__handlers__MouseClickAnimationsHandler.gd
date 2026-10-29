# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/source/match/handlers/MouseClickAnimationsHandler.gd
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
extends Node3D

const MouseClickAnimation = preload("res://source/match/utils/MouseClickAnimation.tscn")


func _ready():
	MatchSignals.terrain_targeted.connect(_on_terrain_targeted)


func _on_terrain_targeted(target_position):
	if (
		get_tree()
		. get_nodes_in_group("selected_units")
		. filter(func(unit): return unit.is_in_group("controlled_units"))
		. is_empty()
	):
		return
	var node = MouseClickAnimation.instantiate()
	node.global_transform = Transform3D(Basis(), target_position)
	add_child(node)
