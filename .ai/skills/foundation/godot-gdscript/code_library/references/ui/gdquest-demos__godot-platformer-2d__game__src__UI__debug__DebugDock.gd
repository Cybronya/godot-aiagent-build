# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/UI/debug/DebugDock.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
extends MarginContainer
# Contains UI widgets that display debug info about the game world

func _input(event: InputEvent) -> void:
	if event.is_action_pressed('toggle_debug_menu'):
		visible = not visible
		accept_event()
