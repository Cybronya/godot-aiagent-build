# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/escoria-dialog-simple/esc_dialog_simple_state_machine.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
extends StateMachine
## Instanciation of this dialogs state machine implementation.

# Constructor
func _init():
	_create_states()
	_add_states_to_machine()
	current_state_name = "idle"
	# This line is very important here: it defines the initial state of the
	# dialogs state machine. Since Escoria can't guess which state is the default one
	# it has to be assigned here. If it happens to be null on initialize() call,
	# an error is triggered.
	start_state = states_map[current_state_name]
	initialize(start_state)


# Creates the states for this state machine.
func _create_states() -> void:
	states_map = {
		"idle": preload("res://addons/escoria-dialog-simple/states/dialog_idle.gd").new(),
		"say":  preload("res://addons/escoria-dialog-simple/states/dialog_say.gd").new(),
		"say_fast":  preload("res://addons/escoria-dialog-simple/states/dialog_say_fast.gd").new(),
		"say_finish":  preload("res://addons/escoria-dialog-simple/states/dialog_say_finish.gd").new(),
		"visible":  preload("res://addons/escoria-dialog-simple/states/dialog_visible.gd").new(),
		"finish":  preload("res://addons/escoria-dialog-simple/states/dialog_finish.gd").new(),
		"interrupt":  preload("res://addons/escoria-dialog-simple/states/dialog_interrupt.gd").new(),
		"choices":  preload("res://addons/escoria-dialog-simple/states/dialog_choices.gd").new()
	}


# Adds any created states into the state machine as children.
func _add_states_to_machine() -> void:
	for key in states_map:
		add_child(states_map[key])
