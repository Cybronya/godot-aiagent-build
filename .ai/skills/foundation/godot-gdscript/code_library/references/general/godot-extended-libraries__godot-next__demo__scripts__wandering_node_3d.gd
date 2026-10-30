# Source:  https://github.com/godot-extended-libraries/godot-next/blob/master/demo/scripts/wandering_node_3d.gd
# Repo:    godot-extended-libraries/godot-next (star 998) | License: MIT | Collected: 2026-10-29
# Commit:  4ac438abe5b4
extends Spatial

var velocity = Vector3()
onready var center = transform.origin

func _ready():
	randomize()


func _physics_process(_delta):
	velocity += Vector3(randf() * 2 - 1, randf() - 0.5, randf() - 0.5) * 0.05
	if velocity.length_squared() > 1:
		velocity *= 0.99
	transform.origin += velocity
	transform.origin = transform.origin.linear_interpolate(center, 0.125)
