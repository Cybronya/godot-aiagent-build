# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/finite_state_machine/debug/states_stack_displayer.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Panel

@onready var fsm_node: Node = get_node(^"../../Player/StateMachine")

func _process(_delta: float) -> void:
	var states_names: String = ""
	var numbers: String = ""
	var index := 0

	for state: Node in fsm_node.states_stack:
		states_names += String(state.name) + "\n"
		numbers += str(index) + "\n"
		index += 1

	%States.text = states_names
	%Numbers.text = numbers
