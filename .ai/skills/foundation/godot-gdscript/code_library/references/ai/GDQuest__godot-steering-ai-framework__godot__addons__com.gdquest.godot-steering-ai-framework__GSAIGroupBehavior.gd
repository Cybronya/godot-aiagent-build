# Source:  https://github.com/GDQuest/godot-steering-ai-framework/blob/master/godot/addons/com.gdquest.godot-steering-ai-framework/GSAIGroupBehavior.gd
# Repo:    GDQuest/godot-steering-ai-framework (star 1588) | License: MIT | Collected: 2026-10-26
# Commit:  master
# Base type for group-based steering behaviors.
# @category - Base types
class_name GSAIGroupBehavior
extends GSAISteeringBehavior

# Container to find neighbors of the agent and calculate group behavior.
var proximity: GSAIProximity

var _callback := Callable(self, "_report_neighbor")


func _init(agent: GSAISteeringAgent, _proximity: GSAIProximity) -> void:
	super._init(agent)
	self.proximity = _proximity


# Internal callback for the behavior to define whether or not a member is
# relevant
# @tags - virtual
func _report_neighbor(_neighbor: GSAISteeringAgent) -> bool:
	return false
