# Source:  https://github.com/godot-fun/godot-start/blob/main/scene/demo01_hello/script/CustomNode.gd
# Repo:    godot-fun/godot-start (star 1106) | License: MIT | Collected: 2026-10-29
# Commit:  115fc06e42f3
@icon("res://icon.svg")

extends Node2D

class_name MyNode

@export var a: int = 1
@export var b: String

func _ready():
	print("my custom node")
	pass
