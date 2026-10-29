# Source:  https://github.com/derkork/godot-statecharts/blob/main/godot_state_charts_examples/ant_hill/pause_controller.gd
# Repo:    derkork/godot-statecharts (star 1623) | License: MIT | Collected: 2026-10-26
# Commit:  76d226a3efac
extends Node


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS

func _input(event:InputEvent) -> void:
	if event is InputEventKey and event.is_pressed() and event.keycode == KEY_SPACE:
		get_tree().paused = not get_tree().paused
		print("Paused ", get_tree().paused)
