# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/source/Main.gd
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
extends Control

@onready var _logos = find_child("Logos")


func _ready():
	_logos.tree_exited.connect(
		get_tree().change_scene_to_file.bind("res://source/main-menu/Main.tscn")
	)
