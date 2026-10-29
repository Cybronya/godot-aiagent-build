# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/monsters/bosses/wild_boar/debug/BossStatesDisplayer.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
tool
extends Panel

func _ready():
	set_as_toplevel(true)

func _on_WildBoar_state_changed(new_state_name):
	$State.text = new_state_name

func _on_WildBoar_phase_changed(new_phase_name):
	$Phase.text = "Phase: " + new_phase_name
