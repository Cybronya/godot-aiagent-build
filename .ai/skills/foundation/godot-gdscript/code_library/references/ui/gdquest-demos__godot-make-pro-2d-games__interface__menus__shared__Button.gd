# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/interface/menus/shared/Button.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Button

func _gui_input(event):
	if event.is_action_pressed('ui_accept'):
		accept_event()
