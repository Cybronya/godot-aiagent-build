# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/vfx/AfterImageVFX.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  master
class_name AfterImageVFX
extends Node2D

@export var sprite:Sprite2D

@export var animation_player:AnimationPlayer

@export var animation:StringName

@export var pool_node:PoolNode

func setup(texture:Texture, hframes:int, vframes:int, frame:int, centered:bool, offset:Vector2, sprite_position:Vector2, world_position:Vector2)->void:
	sprite.texture = texture
	sprite.hframes = hframes
	sprite.vframes = vframes
	sprite.frame = frame
	sprite.centered = centered
	sprite.offset = offset
	sprite.position = sprite_position
	global_position = world_position

func _ready() -> void:
	animation_player.stop()
	animation_player.play(animation)
	animation_player.animation_finished.connect(_on_anim_finished, CONNECT_ONE_SHOT)
	request_ready()

func _on_anim_finished(_anim:StringName)->void:
	pool_node.pool_return()
