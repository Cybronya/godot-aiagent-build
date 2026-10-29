# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/source/generic-scenes-and-nodes/3d/MouseClickAnimation3D.gd
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
extends Node3D
@onready var _animation_player = find_child("AnimationPlayer")


func _ready():
	_animation_player.animation_finished.connect(_on_animation_finished)
	_animation_player.play("fade_out")


func _on_animation_finished(_animation):
	queue_free()
