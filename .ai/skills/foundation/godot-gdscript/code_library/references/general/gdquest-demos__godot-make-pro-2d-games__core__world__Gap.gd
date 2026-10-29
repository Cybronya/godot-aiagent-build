# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/core/world/Gap.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Area2D

func _on_body_entered(body):
	if not body.has_method('fall'):
		return
	body.fall($CollisionShape2D.shape.extents)
