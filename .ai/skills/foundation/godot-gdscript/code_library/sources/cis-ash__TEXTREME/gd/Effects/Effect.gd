extends Node2D
var letter = ""

export(Array, NodePath) var particles : Array = []

func _ready():
	for i in particles:
		get_node(i).emitting = true

func destroy(dummyarg = ""):
	queue_free()
	pass