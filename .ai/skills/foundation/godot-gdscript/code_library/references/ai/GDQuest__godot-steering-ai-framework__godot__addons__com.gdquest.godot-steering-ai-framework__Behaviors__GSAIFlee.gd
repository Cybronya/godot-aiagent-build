# Source:  https://github.com/GDQuest/godot-steering-ai-framework/blob/master/godot/addons/com.gdquest.godot-steering-ai-framework/Behaviors/GSAIFlee.gd
# Repo:    GDQuest/godot-steering-ai-framework (star 1588) | License: MIT | Collected: 2026-10-26
# Commit:  master
# Calculates acceleration to take an agent directly away from a target agent.
# @category - Individual behaviors
class_name GSAIFlee
extends GSAISeek


func _init(agent: GSAISteeringAgent, target: GSAIAgentLocation) -> void:
	super._init(agent, target)


func _calculate_steering(acceleration: GSAITargetAcceleration) -> void:
	acceleration.linear = (
		(agent.position - target.position).normalized()
		* agent.linear_acceleration_max
	)
	acceleration.angular = 0
