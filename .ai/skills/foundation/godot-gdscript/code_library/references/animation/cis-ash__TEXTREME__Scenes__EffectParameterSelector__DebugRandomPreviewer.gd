# Source:  https://github.com/cis-ash/TEXTREME/blob/master/Scenes/EffectParameterSelector/DebugRandomPreviewer.gd
# Repo:    cis-ash/TEXTREME (star 801) | License: MIT | Collected: 2026-10-31
# Commit:  673dc09d9132
tool
extends Node2D

export var buffer_size := 60

var buffer := []

func _draw():
	if buffer.size() > 60:
		buffer.pop_front()
	
	buffer.push_back(get_parent().get_random_vector() * 25.0)

	for i in buffer:
		draw_circle(i, 1.0, Color(1.0, 1.0, 0.0, 1.0))

func _process(delta):
	update()
