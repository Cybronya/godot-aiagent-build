# Source:  https://github.com/foxssake/netfox/blob/main/examples/forest-brawl/scripts/play-random-3d.gd
# Repo:    foxssake/netfox (star 1121) | License: MIT | Collected: 2026-10-29
# Commit:  cf5189d18e98
extends AudioStreamPlayer3D
class_name PlayRandomStream3D

@export var sounds: Array[AudioStream] = []

static var idx = 0

func _ready():
	if autoplay:
		play_random()

func play_random():
	stream = sounds.pick_random()
	play()
