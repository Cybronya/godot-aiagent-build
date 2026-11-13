# Source:  https://github.com/cis-ash/TEXTREME/blob/master/Effects/GenericEffect.gd
# Repo:    cis-ash/TEXTREME (star 801) | License: MIT | Collected: 2026-10-31
# Commit:  673dc09d9132
extends Node2D

export(Array, NodePath) var particles : Array = []

func _ready():
	for i in particles:
		get_node(i).emitting = true

func on_setup_done():
	position = (get_parent() as Effect).positions[0]