# Source:  https://github.com/ramokz/phantom-camera/blob/main/addons/phantom_camera/examples/scripts/2D/2d_trigger_area.gd
# Repo:    ramokz/phantom-camera (star 3640) | License: MIT | Collected: 2026-10-26
# Commit:  9874dfe68827
extends Area2D

@export var area_pcam: PhantomCamera2D

func _ready() -> void:
	connect("area_entered", _entered_area)
	connect("area_exited", _exited_area)

func _entered_area(area_2d: Area2D) -> void:
	if area_2d.get_parent() is CharacterBody2D:
		area_pcam.set_priority(20)

func _exited_area(area_2d: Area2D) -> void:
	if area_2d.get_parent() is CharacterBody2D:
		area_pcam.set_priority(0)

