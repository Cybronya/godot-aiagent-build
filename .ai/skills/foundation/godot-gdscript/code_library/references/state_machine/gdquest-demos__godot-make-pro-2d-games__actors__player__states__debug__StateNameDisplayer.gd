# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/actors/player/states/debug/StateNameDisplayer.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Label

func _on_StateMachine_state_changed(current_state):
	text = current_state.name
