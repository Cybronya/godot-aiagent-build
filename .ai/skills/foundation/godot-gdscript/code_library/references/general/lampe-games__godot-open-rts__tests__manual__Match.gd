# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/tests/manual/Match.gd
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
extends "res://source/match/Match.gd"

@export var allow_resources_deficit_spending = true


func _ready():
	find_child("MatchEndHandler").queue_free()
	FeatureFlags.allow_resources_deficit_spending = allow_resources_deficit_spending
	super()
