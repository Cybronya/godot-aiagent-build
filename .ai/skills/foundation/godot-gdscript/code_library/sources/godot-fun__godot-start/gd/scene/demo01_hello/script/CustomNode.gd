@icon("res://icon.svg")

extends Node2D

class_name MyNode

@export var a: int = 1
@export var b: String

func _ready():
	print("my custom node")
	pass
