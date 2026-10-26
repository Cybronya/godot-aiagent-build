# Source:  https://github.com/GDQuest/godot-steering-ai-framework/blob/master/godot/addons/com.gdquest.godot-steering-ai-framework/Behaviors/GSAISeek.gd
# Repo:    GDQuest/godot-steering-ai-framework (star 1588) | License: MIT | Collected: 2026-10-26
# Commit:  master
# Calculates an acceleration to take an agent to a target agent's position
# directly.
# @category - Individual behaviors
class_name GSAISeek
extends GSAISteeringBehavior

# The target that the behavior aims to move the agent to.
var target: GSAIAgentLocation


func _init(agent: GSAISteeringAgent, _target: GSAIAgentLocation) -> void:
	super._init(agent)
	self.target = _target


func _calculate_steering(acceleration: GSAITargetAcceleration) -> void:
	acceleration.linear = (
		(target.position - agent.position).normalized()
		* agent.linear_acceleration_max
	)
	acceleration.angular = 0
