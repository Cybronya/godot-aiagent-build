# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/actors/weapons/sword/WeaponPivot.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Position2D

func _on_Player_direction_changed(new_direction):
	rotation = new_direction.angle()
	show_behind_parent = new_direction == Vector2(0, -1)
