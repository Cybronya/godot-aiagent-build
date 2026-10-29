# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/ui/title_screen/Quit.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
extends Node

@export var button:Button

func _ready()->void:
	button.pressed.connect(pressed)

func pressed()->void:
	get_tree().quit()
