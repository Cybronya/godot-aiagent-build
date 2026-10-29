# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Modules/Style/node_style.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  701b67bbe601
class_name DialogicNode_StyleLayer
extends Control

## Control node that is hidden and shown based on the current dialogic style.

## The name this layer listens to
@export var layer_name: String = 'Default'


func _ready() -> void:
	if layer_name.is_empty():
		layer_name = name
	add_to_group('dialogic_style_layer')
