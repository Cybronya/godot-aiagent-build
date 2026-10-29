# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/ui/pause_screen/GamepadDisconnectPause.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
class_name GamepadDisconnectPause
extends Node

@export var pause_resource:BoolResource

func _ready()->void:
	Input.joy_connection_changed.connect(on_joy_connection_changed)

func on_joy_connection_changed(_device: int, connected: bool)->void:
	if connected:
		return
	if pause_resource.value == true:
		return
	pause_resource.set_value(true)
