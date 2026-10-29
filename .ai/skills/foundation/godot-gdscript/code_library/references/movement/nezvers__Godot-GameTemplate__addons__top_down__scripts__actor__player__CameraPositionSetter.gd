# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/actor/player/CameraPositionSetter.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
class_name CameraPositionSetter
extends Node

@export var camera_reference:ReferenceNodeResource
@export var position_resource:Vector2Resource
@export var target_node:Node2D

func _ready()->void:
	assert(camera_reference != null)
	camera_reference.listen(self, _on_camera_reference)
	
	# Same player will be moved between scenes
	tree_entered.connect(_on_camera_reference)

func _on_camera_reference()->void:
	if !is_inside_tree():
		return
	if camera_reference.node == null:
		return
	position_resource.set_value(target_node.global_position)
	camera_reference.node.set_target_position(position_resource)

func _physics_process(delta: float)->void:
	position_resource.set_value(target_node.global_position)
