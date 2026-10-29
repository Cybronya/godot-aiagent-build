# Source:  https://github.com/blackears/cyclopsLevelBuilder/blob/master/godot/test/test_vertex_dict_index.gd
# Repo:    blackears/cyclopsLevelBuilder (star 1639) | License: MIT | Collected: 2026-10-29
# Commit:  ea41feaab5dd
extends Control


# Called when the node enters the scene tree for the first time.
func _ready():
	var a:PackedFloat32Array = [1, 2, 3]
	var b:PackedFloat32Array = [1, 2, 3]
	var c:PackedFloat32Array = [1, 2, 6]
	
	var dict:Dictionary
	dict[a] = "A"
	dict[b] = "B"
	dict[c] = "C"
	
	print("has A ", dict.has(a))
	print(dict)
	pass # Replace with function body.


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta):
	pass
