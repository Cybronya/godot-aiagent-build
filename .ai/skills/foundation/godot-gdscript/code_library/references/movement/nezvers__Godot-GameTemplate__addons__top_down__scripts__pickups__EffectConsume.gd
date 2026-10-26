# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/pickups/EffectConsume.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  master
class_name EffectConsume
extends Node

@export var data_transmitter:DataChannelTransmitter
@export var animation_player:AnimationPlayer
@export var fade_out_animation:StringName = "fade_out"
@export var sounds_resource:SoundResource

func _ready()->void:
	data_transmitter.set_enabled(true)
	data_transmitter.success.connect(_on_success, CONNECT_ONE_SHOT)
	request_ready()

func _on_success()->void:
	data_transmitter.set_enabled(false)
	sounds_resource.play_managed()
	animation_player.play(fade_out_animation)
