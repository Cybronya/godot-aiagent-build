# Source:  https://github.com/MarcoFazioRandom/Virtual-Joystick-Godot/blob/Main/addons/virtual_joystick/virtual_joystick_plugin.gd
# Repo:    MarcoFazioRandom/Virtual-Joystick-Godot (star 991) | License: MIT | Collected: 2026-10-29
# Commit:  b90891ee9908
@tool
extends EditorPlugin


func _enter_tree():
	add_custom_type("Virtual Joystick", "Control", preload("virtual_joystick_instantiator.gd"), preload("virtual_joystick_icon.png"))


func _exit_tree():
	remove_custom_type("Virtual Joystick")
