# Source:  https://github.com/cis-ash/TEXTREME/blob/master/Effects/PasteEffect/PasteEffect.gd
# Repo:    cis-ash/TEXTREME (star 801) | License: MIT | Collected: 2026-10-31
# Commit:  673dc09d9132
extends Node2D

func _ready():
	$LeftSpark.emitting = true
	$RightSpark.emitting = true

func on_setup_done():
	var parent := (get_parent() as Effect)
	var effect_scale = parent.font.get_height() / 12.0
	$LeftSpark.position = parent.position_before
	$RightSpark.position = parent.positions[parent.positions.size() - 1]
	$LeftSpark.scale = Vector2(1, 1) * effect_scale
	$RightSpark.scale = Vector2(1, 1) * effect_scale
