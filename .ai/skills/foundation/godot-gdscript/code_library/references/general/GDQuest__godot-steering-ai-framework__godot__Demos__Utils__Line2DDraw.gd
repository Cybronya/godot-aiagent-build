# Source:  https://github.com/GDQuest/godot-steering-ai-framework/blob/master/godot/Demos/Utils/Line2DDraw.gd
# Repo:    GDQuest/godot-steering-ai-framework (star 1588) | License: MIT | Collected: 2026-10-26
# Commit:  master
@tool
extends Line2D

@export var inner_color := Color(): set = set_inner_color


func _draw() -> void:
	draw_colored_polygon(points, inner_color)


func set_inner_color(val: Color) -> void:
	inner_color = val
	queue_redraw()
