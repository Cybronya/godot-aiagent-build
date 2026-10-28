# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/common/panku_button.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  master
class_name PankuButton extends Control

signal pressed
signal button_down
signal button_up

@export
var button:Button

@export
var trect:TextureRect

@export
var label:Label

var icon:
	set(v):
		trect.texture = v
	get:
		return trect.texture

var text:
	set(v):
		label.text = v
	get:
		return label.text

func _ready():
	
	button.pressed.connect(
		func():
			pressed.emit()
	)
	button.button_down.connect(
		func(): button_down.emit()
	)
	button.button_up.connect(
		func(): button_up.emit()
	)
