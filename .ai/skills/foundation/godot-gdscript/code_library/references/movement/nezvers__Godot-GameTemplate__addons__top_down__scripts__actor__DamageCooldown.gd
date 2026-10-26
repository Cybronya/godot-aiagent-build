# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/actor/DamageCooldown.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  master
class_name DamageCooldown
extends Node

@export var resource_node:ResourceNode
@export var cooldown_time:float = 0.0

func _ready()->void:
	var _damage_bool:BoolResource = resource_node.get_resource("damage")
	var _health_resource:HealthResource = resource_node.get_resource("health")
	_health_resource.damaged.connect(_on_damaged.bind(_damage_bool))

func _on_damaged(damage_bool:BoolResource)->void:
	if cooldown_time == 0.0:
		return
	damage_bool.set_value(false)
	
	# TODO: Potential bug if something is also toggling damage_bool 
	var _tween:Tween = create_tween()
	_tween.tween_callback(damage_bool.set_value.bind(true)).set_delay(cooldown_time)
