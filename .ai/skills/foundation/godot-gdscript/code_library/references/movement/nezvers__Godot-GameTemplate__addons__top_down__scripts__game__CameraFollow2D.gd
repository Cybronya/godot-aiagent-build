# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/game/CameraFollow2D.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
#class_name CameraFollow2D
extends Camera2D

@export var follow:bool = true
@export var lerp_speed:float = 5.0
@export var target_position:Vector2Resource

func _ready()->void:
	set_target_position(target_position)
	set_physics_process(follow && target_position != null)

## Toggles camera's following functionality
func set_follow(value:bool)->void:
	follow = value
	set_physics_process(follow && target_position != null)

func set_target_position(value:Vector2Resource)->void:
	target_position = value
	global_position = target_position.value
	set_physics_process(follow && target_position != null)

func _physics_process(delta:float)->void:
	global_position = global_position.lerp(target_position.value, lerp_speed * delta)
