# Source:  https://github.com/cis-ash/TEXTREME/blob/master/Effects/OtherEffect/OtherEffect.gd
# Repo:    cis-ash/TEXTREME (star 801) | License: MIT | Collected: 2026-10-31
# Commit:  673dc09d9132
extends Node2D

func _ready():
	$Sparks.emitting = true

func on_setup_done():
	var parent := get_parent() as Effect
	position = parent.positions[0]
	scale = Vector2(1, 1) * (parent.font.get_height() / 12.0)
