# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/vfx/particles/fiery_cloud/FireryCloud.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
tool
extends Particles2D

export(float) var TIME_SCALE = 1.0
export(float) var RADIUS = 200.0
export(Vector2) var OFFSET = Vector2()

export(bool) var active = false setget set_active

var time = 0.0

func _process(delta):
	time += delta
	var time_scaled = TIME_SCALE * time
	position = Vector2(
		cos(time_scaled) * RADIUS, 
		sin(time_scaled) * RADIUS
	) 
	position += OFFSET

func set_active(value):
	active = value
	set_process(active)
	if not active:
		position = Vector2()