extends Node

var nodes := {} #stores all scenes that can be loaded as utilities

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	#check utilities folder for all scenes and load into nodes dictionary
	#var dir = DirAccess.open("res://scenes/Nodes/utilities/")
	#if dir:
		#for file in dir.get_files():
			#if file.ends_with(".tscn"):
				#var name = file.get_basename()
				#var path = "res://scenes/Nodes/utilities/" + file
				#nodes[name] = load(path)
	nodes["calculator"] = load("res://scenes/Nodes/utilities/calculator.tscn")
	nodes["convert_time"] = load("res://scenes/Nodes/utilities/convert_time.tscn")
	nodes["inputfile"] = load("res://scenes/Nodes/utilities/inputfile.tscn")
	nodes["notes"] = load("res://scenes/Nodes/utilities/notes.tscn")
	nodes["note_to_hz"] = load("res://scenes/Nodes/utilities/note_to_hz.tscn")
	nodes["outputfile"] = load("res://scenes/Nodes/utilities/outputfile.tscn")
	nodes["preview"] = load("res://scenes/Nodes/utilities/preview.tscn")
