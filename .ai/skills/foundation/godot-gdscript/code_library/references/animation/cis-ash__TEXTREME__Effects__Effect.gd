# Source:  https://github.com/cis-ash/TEXTREME/blob/master/Effects/Effect.gd
# Repo:    cis-ash/TEXTREME (star 801) | License: MIT | Collected: 2026-10-31
# Commit:  673dc09d9132
extends Node2D
var letter = ""

export(Array, NodePath) var particles : Array = []

func _ready():
	for i in particles:
		get_node(i).emitting = true

func destroy(dummyarg = ""):
	queue_free()
	pass