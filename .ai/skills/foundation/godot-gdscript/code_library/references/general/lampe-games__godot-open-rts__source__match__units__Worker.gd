# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/source/match/units/Worker.gd
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
extends "res://source/match/units/Unit.gd"

var resource_a = 0
var resource_b = 0
var resources_max = null


func is_full():
	assert(resource_a + resource_b <= resources_max, "worker capacity was exceeded somehow")
	return resource_a + resource_b == resources_max
