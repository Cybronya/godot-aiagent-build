# Source:  https://github.com/GodotVR/godot-xr-tools/blob/master/scenes/pointer_demo/objects/keyboard_test_screen.gd
# Repo:    GodotVR/godot-xr-tools (star 740) | License: MIT | Collected: 2026-10-31
# Commit:  6c6189bdfcdf
extends Node2D


func _on_ClearButton_pressed():
	$Container/Line1/TextEdit.text = ""
	$Container/Line2/TextEdit.text = ""
	$Container/Line3/TextEdit.text = ""
