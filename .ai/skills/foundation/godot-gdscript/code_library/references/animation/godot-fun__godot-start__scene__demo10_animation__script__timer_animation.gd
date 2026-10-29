# Source:  https://github.com/godot-fun/godot-start/blob/main/scene/demo10_animation/script/timer_animation.gd
# Repo:    godot-fun/godot-start (star 1106) | License: MIT | Collected: 2026-10-29
# Commit:  115fc06e42f3
extends Sprite2D


func _on_timer_timeout():
	if frame < 5:
		frame += 1
	else:
		frame = 0
	pass
