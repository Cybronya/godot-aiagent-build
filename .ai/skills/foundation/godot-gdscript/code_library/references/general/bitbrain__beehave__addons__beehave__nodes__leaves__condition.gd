# Source:  https://github.com/bitbrain/beehave/blob/godot-4.x/addons/beehave/nodes/leaves/condition.gd
# Repo:    bitbrain/beehave (star 3312) | License: MIT | Collected: 2026-10-26
# Commit:  fe589153fa78
## Conditions are leaf nodes that either return SUCCESS or FAILURE depending on
## a single simple condition. They should never return `RUNNING`.
@tool
@icon("../../icons/condition.svg")
class_name ConditionLeaf extends Leaf


func get_class_name() -> Array[StringName]:
	var classes := super()
	classes.push_back(&"ConditionLeaf")
	return classes
