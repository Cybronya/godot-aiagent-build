# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/top_down/scripts/input/save_controls_event.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
extends Node

@export var rebinding_panel:Control
@export var action_resource:ActionResource

func _ready()->void:
	assert(action_resource != null)
	assert(rebinding_panel != null)
	rebinding_panel.visibility_changed.connect(on_visibility_changed)

func on_visibility_changed()->void:
	if rebinding_panel.visible:
		return
	assert(!action_resource.resource_path.is_empty())
	action_resource.save_resource()
