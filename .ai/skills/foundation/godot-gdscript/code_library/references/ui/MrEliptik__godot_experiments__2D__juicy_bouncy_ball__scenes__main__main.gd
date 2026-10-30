# Source:  https://github.com/MrEliptik/godot_experiments/blob/master/2D/juicy_bouncy_ball/scenes/main/main.gd
# Repo:    MrEliptik/godot_experiments (star 1034) | License: MIT | Collected: 2026-10-29
# Commit:  4baec7290110
extends Node2D

var tween: Tween

@onready var bg = $BG

func _ready():
	Globals.camera = $Camera2D

func scale_bg() -> void:
	if tween and tween.is_running():
		tween.kill()
	tween = create_tween()
	var initial_scale: Vector2 = bg.texture_scale
	tween.tween_property(bg, "texture_scale", bg.texture_scale * 0.75, 0.1) \
						.set_trans(Tween.TRANS_ELASTIC).set_ease(Tween.EASE_OUT)
	tween.tween_property(bg, "texture_scale", initial_scale, 0.3) \
						.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN_OUT)

func _on_ball_hit():
	scale_bg()
