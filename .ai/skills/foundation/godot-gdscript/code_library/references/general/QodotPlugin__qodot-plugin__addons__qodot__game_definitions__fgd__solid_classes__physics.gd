# Source:  https://github.com/QodotPlugin/qodot-plugin/blob/master/addons/qodot/game_definitions/fgd/solid_classes/physics.gd
# Repo:    QodotPlugin/qodot-plugin (star 982) | License: MIT | Collected: 2026-10-29
# Commit:  4731a36dec69
class_name PhysicsEntity
extends RigidBody
tool

export(Dictionary) var properties setget set_properties

func set_properties(new_properties : Dictionary) -> void:
	if(properties != new_properties):
		properties = new_properties
		update_properties()

func update_properties():
	if 'velocity' in properties:
		linear_velocity = properties['velocity']

	if 'mass' in properties:
		mass = properties.mass


func use():
	bounce()

func bounce():
	linear_velocity.y = 10
