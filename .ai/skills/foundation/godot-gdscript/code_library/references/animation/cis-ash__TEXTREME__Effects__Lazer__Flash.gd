# Source:  https://github.com/cis-ash/TEXTREME/blob/master/Effects/Lazer/Flash.gd
# Repo:    cis-ash/TEXTREME (star 801) | License: MIT | Collected: 2026-10-31
# Commit:  673dc09d9132
extends Control

func _ready():
	call_deferred("start")

func start():
	var parent := (get_parent() as Effect)
	rect_position.y = parent.positions[0].y - parent.font.get_height() / 2
	rect_size.y = parent.font.get_height()
	$AnimationPlayer.play("Fadeout")
