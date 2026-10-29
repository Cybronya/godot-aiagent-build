extends Sprite2D


func _on_timer_timeout():
	if frame < 5:
		frame += 1
	else:
		frame = 0
	pass
