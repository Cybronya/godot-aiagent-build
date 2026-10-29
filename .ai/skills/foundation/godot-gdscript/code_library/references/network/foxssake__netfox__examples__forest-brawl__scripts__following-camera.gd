# Source:  https://github.com/foxssake/netfox/blob/main/examples/forest-brawl/scripts/following-camera.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends Camera3D
class_name FollowingCamera

@export var distance: float = 4.0
@export var approach_time: float = 0.125
@export var target: Node3D

func _ready():
	NetworkTime.on_tick.connect(_tick)

func _tick(delta: float, _t: int):
	if not target:
		return

	var desired_pos = target.global_position
	desired_pos += transform.basis.z * distance

	var diff = desired_pos - global_position
	var dst = diff.length()
	diff = diff.normalized()

	global_position += diff * minf(dst / approach_time * delta, dst)
