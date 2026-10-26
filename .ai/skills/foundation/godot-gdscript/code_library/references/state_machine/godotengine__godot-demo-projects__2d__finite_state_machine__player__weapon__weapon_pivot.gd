# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/finite_state_machine/player/weapon/weapon_pivot.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Marker2D

var z_index_start := 0

func _ready() -> void:
	owner.direction_changed.connect(_on_Parent_direction_changed)
	z_index_start = z_index


func _on_Parent_direction_changed(direction: Vector2) -> void:
	rotation = direction.angle()
	match direction:
		Vector2.UP:
			z_index = z_index_start - 1
		_:
			z_index = z_index_start
