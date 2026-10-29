# Source:  https://github.com/derkork/godot-statecharts/blob/main/addons/godot_state_charts/atomic_state.gd
# Repo:    derkork/godot-statecharts (star 1623) | License: MIT | Collected: 2026-10-26
# Commit:  76d226a3efac
@tool
@icon("atomic_state.svg")
## This is a state that has no sub-states.
class_name AtomicState
extends StateChartState

func _handle_transition(transition:Transition, source:StateChartState) -> void:
	# resolve the target state
	var target := transition.resolve_target()
	if target == null:
		push_error("The target state '" + str(transition.to) + "' of the transition from '" + source.name + "' is not a state.")
		return
	# atomic states cannot transition, so we need to ask the parent
	# ask the parent
	get_parent()._handle_transition(transition, source)


func _get_configuration_warnings() -> PackedStringArray:
	var warnings := super._get_configuration_warnings()
	# check if we have any child nodes which are not transitions
	for child in get_children():
		if child is StateChartState:
			warnings.append("Atomic states cannot have child states. These will be ignored.")
			break
	return warnings
