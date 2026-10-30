# Source:  https://github.com/godot-extended-libraries/godot-next/blob/master/demo/scripts/wandering_node_2d.gd
# Repo:    godot-extended-libraries/godot-next (star 998) | License: MIT | Collected: 2026-10-29
# Commit:  4ac438abe5b4
extends Node2D

var velocity = Vector2()
onready var center = position

func _ready():
	randomize()


func _physics_process(_delta):
	velocity += Vector2(randf() - 0.5, randf() - 0.5)
	if velocity.length_squared() > 10:
		velocity *= 0.99
	position += velocity
	position = position.linear_interpolate(center, 0.03).round()
