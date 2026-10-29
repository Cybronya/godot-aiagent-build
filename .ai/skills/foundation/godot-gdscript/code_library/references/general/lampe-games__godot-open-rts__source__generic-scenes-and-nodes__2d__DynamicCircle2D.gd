# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/source/generic-scenes-and-nodes/2d/DynamicCircle2D.gd
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
@tool
extends Node2D

@export var color = Color.WHITE
@export var radius = 15


func _draw():
	draw_circle(Vector2(0, 0), radius, color)
