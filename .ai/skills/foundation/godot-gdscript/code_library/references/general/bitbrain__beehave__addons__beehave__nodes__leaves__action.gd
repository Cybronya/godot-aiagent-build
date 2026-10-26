# Source:  https://github.com/bitbrain/beehave/blob/godot-4.x/addons/beehave/nodes/leaves/action.gd
# Repo:    bitbrain/beehave (star 3312) | License: MIT | Collected: 2026-10-26
# Commit:  godot-4.x
## Actions are leaf nodes that define a task to be performed by an actor.
## Their execution can be long running, potentially being called across multiple
## frame executions. In this case, the node should return `RUNNING` until the
## action is completed.
@tool
@icon("../../icons/action.svg")
class_name ActionLeaf extends Leaf


func get_class_name() -> Array[StringName]:
	var classes := super()
	classes.push_back(&"ActionLeaf")
	return classes
