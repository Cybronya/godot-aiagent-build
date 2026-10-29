# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/damage/ResetHealth.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
class_name ResetHealth
extends Node

@export var resource_node:ResourceNode

## Player's health is globally used and stays the same
func _ready()->void:
	var _health_resource:HealthResource = resource_node.get_resource("health")
	_health_resource.reset_resource()
	
	_health_resource.dead.connect(owner.queue_free)
