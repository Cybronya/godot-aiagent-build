# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/gui/accessibility/controls.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Control


func _ready() -> void:
	$LineEditName.grab_focus() # Accessible UI should always have keyboard focus, since it is a main way of interacting with UI.


func _on_button_set_pressed() -> void:
	$Panel/LabelRegion.text = $LineEditLiveReg.text # Set live region text.
