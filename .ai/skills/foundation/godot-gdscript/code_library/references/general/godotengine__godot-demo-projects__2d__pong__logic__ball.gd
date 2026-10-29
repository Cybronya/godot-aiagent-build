# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/pong/logic/ball.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Area2D

const DEFAULT_SPEED = 100.0

var _speed := DEFAULT_SPEED
var direction := Vector2.LEFT

@onready var _initial_pos := position

func _process(delta: float) -> void:
	_speed += delta * 2
	position += _speed * delta * direction


func reset() -> void:
	direction = Vector2.LEFT
	position = _initial_pos
	_speed = DEFAULT_SPEED
