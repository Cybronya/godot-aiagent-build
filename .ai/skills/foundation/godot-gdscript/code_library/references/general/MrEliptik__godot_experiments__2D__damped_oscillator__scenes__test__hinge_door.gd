# Source:  https://github.com/MrEliptik/godot_experiments/blob/master/2D/damped_oscillator/scenes/test/hinge_door.gd
# Repo:    MrEliptik/godot_experiments (star 1034) | License: MIT | Collected: 2026-10-29
# Commit:  4baec7290110
extends Node2D

@export var spring: float = 150.0
@export var damp: float = 10.0
@export var multiplier: float = 25.0

var displacement: float = 0.0 
var velocity: float = 0.0

func _ready():
	pass # Replace with function body.

func _process(delta):
	var force = -spring * displacement + damp * velocity
	velocity -= force * delta
	displacement -= velocity * delta
	
	rotation = displacement

func _on_area_2d_body_entered(body):
	velocity = body.velocity.normalized().x * multiplier
