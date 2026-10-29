# Source:  https://github.com/lampe-games/godot-open-rts/blob/main/source/Logos.gd
# Repo:    lampe-games/godot-open-rts (star 1136) | License: MIT | Collected: 2026-10-29
# Commit:  a628ad3bb6a9
extends Control

@onready var _animation_player = find_child("AnimationPlayer")


func _ready():
	if not FeatureFlags.show_logos_on_startup:
		queue_free()
		return
	_animation_player.animation_finished.connect(func(_animation_name): queue_free())
	_animation_player.play("animate_logos")
