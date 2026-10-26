# Source:  https://github.com/derkork/godot-statecharts/blob/main/addons/godot_state_charts/all_of_guard.gd
# Repo:    derkork/godot-statecharts (star 1623) | License: MIT | Collected: 2026-10-26
# Commit:  main
@tool
@icon("all_of_guard.svg")

## A composite guard that is satisfied when all of its guards are satisfied.
class_name AllOfGuard
extends Guard

## The guards that need to be satisified. When empty, returns true.
@export var guards:Array[Guard] = [] 

func is_satisfied(context_transition:Transition, context_state:StateChartState) -> bool:
	for guard in guards:
		if not guard.is_satisfied(context_transition, context_state):
			return false
	return true

	
func get_supported_trigger_types() -> int:
	var supported_trigger_types:int = StateChart.TriggerType.NONE
	for guard in guards:
		supported_trigger_types |= guard.get_supported_trigger_types()
	return supported_trigger_types
