# Source:  https://github.com/MrEliptik/godot_experiments/blob/master/2D/polygon_tools/scenes/obstacle/obstacle.gd
# Repo:    MrEliptik/godot_experiments (star 1034) | License: MIT | Collected: 2026-10-29
# Commit:  4baec7290110
extends StaticBody2D

@onready var polygon_2d = $Polygon2D
@onready var collision_polygon_2d = $CollisionPolygon2D
@onready var border_polygon = $BorderPolygon

func _ready():
	collision_polygon_2d.polygon = polygon_2d.polygon
	border_polygon.polygon = polygon_2d.polygon
