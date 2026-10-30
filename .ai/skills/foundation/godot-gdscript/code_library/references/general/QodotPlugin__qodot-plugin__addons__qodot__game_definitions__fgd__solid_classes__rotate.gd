# Source:  https://github.com/QodotPlugin/qodot-plugin/blob/master/addons/qodot/game_definitions/fgd/solid_classes/rotate.gd
# Repo:    QodotPlugin/qodot-plugin (star 982) | License: MIT | Collected: 2026-10-29
# Commit:  4731a36dec69
class_name QodotRotateEntity
extends KinematicBody

export(Dictionary) var properties setget set_properties

var rotate_axis := Vector3.UP
var rotate_speed := 360.0

func set_properties(new_properties : Dictionary) -> void:
	if(properties != new_properties):
		properties = new_properties
		update_properties()

func update_properties():
	if 'axis' in properties:
		rotate_axis = properties['axis']

	if 'speed' in properties:
		rotate_speed = properties['speed']

func _ready() -> void:
	update_properties()

func _process(delta: float) -> void:
	rotate(rotate_axis, deg2rad(rotate_speed * delta))
