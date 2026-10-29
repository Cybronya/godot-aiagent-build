# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/monsters/bosses/wild_boar/debug/StatesStackDisplayer.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
tool
extends Panel

func _ready():
	set_as_toplevel(true)

func _on_Player_state_changed(states_stack):
	var states_names = ''
	var numbers = ''
	var index = 0
	for state in states_stack:
		states_names += state.get_name() + '\n'
		numbers += str(index) + '\n'
		index += 1

	$States.text = states_names
	$Numbers.text = numbers

