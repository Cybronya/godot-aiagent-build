# Source:  https://github.com/GDQuest/godot-steering-ai-framework/blob/master/godot/Demos/PursueSeek/BoundaryManager.gd
# Repo:    GDQuest/godot-steering-ai-framework (star 1588) | License: MIT | Collected: 2026-10-26
# Commit:  9d7cf0deff80
extends Node2D
# Wraps the ships' positions around the world border.

var _world_bounds: Vector2


func _ready() -> void:
	_world_bounds = Vector2(
		ProjectSettings["display/window/size/viewport_width"], ProjectSettings["display/window/size/viewport_height"]
	)


func _physics_process(_delta: float) -> void:
	for ship in get_children():
		ship.position = ship.position.posmodv(_world_bounds)
