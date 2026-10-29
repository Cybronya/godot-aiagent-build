# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/source/main-menu/Credits.gd
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
extends Control

@onready var _rich_text_label = find_child("RichTextLabel")


func _ready():
	_rich_text_label.text = (
		_rich_text_label
		. text
		. replace("CORE_CONTRIBUTORS", tr("CORE_CONTRIBUTORS"))
		. replace("ASSETS", tr("ASSETS"))
	)


func _on_back_button_pressed():
	get_tree().change_scene_to_file("res://source/main-menu/Main.tscn")
