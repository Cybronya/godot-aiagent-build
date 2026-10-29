# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/great_games_library/static/Drawer/Drawer.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
extends Node2D
class_name Drawer

static func draw_ring(node:CanvasItem, radius:float, resolution:int, rotated:float = 0.0, color:Color = Color.WHITE, width:float = -1)->void:
	var increments: float = TAU / resolution
	var rad: = rotated
	var to: = Vector2.ZERO
	var from: = Vector2(cos(rad)*radius, sin(rad)*radius)
	for i in resolution:
		rad = rotated + increments * (i+1)
		to = Vector2(cos(rad)*radius, sin(rad)*radius)
		node.draw_line(from, to, color, width)
		from = to
