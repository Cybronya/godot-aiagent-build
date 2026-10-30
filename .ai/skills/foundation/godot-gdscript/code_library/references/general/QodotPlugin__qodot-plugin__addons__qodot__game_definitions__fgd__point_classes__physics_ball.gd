# Source:  https://github.com/QodotPlugin/qodot-plugin/blob/master/addons/qodot/game_definitions/fgd/point_classes/physics_ball.gd
# Repo:    QodotPlugin/qodot-plugin (star 982) | License: MIT | Collected: 2026-10-29
# Commit:  4731a36dec69
class_name PhysicsBall
extends PhysicsEntity
tool

func update_properties():
	.update_properties()
	if 'size' in properties:
		$MeshInstance.mesh.radius = properties.size * 0.5
		$MeshInstance.mesh.height = properties.size

		$CollisionShape.shape.radius = properties.size * 0.5


func use():
	bounce()

func bounce():
	linear_velocity.y = 10
