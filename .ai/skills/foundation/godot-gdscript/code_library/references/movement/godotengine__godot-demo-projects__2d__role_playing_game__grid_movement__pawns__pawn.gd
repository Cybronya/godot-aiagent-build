# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/role_playing_game/grid_movement/pawns/pawn.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
class_name Pawn
extends Node2D

enum CellType {
	ACTOR,
	OBSTACLE,
	OBJECT,
}

@export var type := CellType.ACTOR

var active: bool = true: set = set_active

func set_active(value: bool) -> void:
	active = value
	set_process(value)
	set_process_input(value)
