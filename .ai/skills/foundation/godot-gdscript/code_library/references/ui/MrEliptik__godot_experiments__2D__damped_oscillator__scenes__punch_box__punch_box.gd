# Source:  https://github.com/MrEliptik/godot_experiments/blob/master/2D/damped_oscillator/scenes/punch_box/punch_box.gd
# Repo:    MrEliptik/godot_experiments (star 1034) | License: MIT | Collected: 2026-10-29
# Commit:  4baec7290110
extends Node2D

@export var spring: float = 150.0
@export var damp: float = 10.0
@export var multiplier: float = 50.0

var displacement: float = 0.0 
var velocity: float = 0.0

@onready var line = $Line2D
@onready var fist = $Glove

func _ready():
	pass

func _process(delta):
	if Input.is_action_just_pressed("ui_accept"):
		velocity = -50.0
	
	var force = -spring * displacement - damp * velocity
	velocity += force * delta
	displacement += velocity * delta
	
	fist.position.x = -displacement * multiplier
	
	# Draw line to the fist
	line.set_point_position(1, Vector2(fist.position.x, 0))
