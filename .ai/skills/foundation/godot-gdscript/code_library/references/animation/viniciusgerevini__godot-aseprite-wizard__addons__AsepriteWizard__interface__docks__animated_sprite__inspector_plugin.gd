# Source:  https://github.com/viniciusgerevini/godot-aseprite-wizard/blob/godot_4/addons/AsepriteWizard/interface/docks/animated_sprite/inspector_plugin.gd
# Repo:    viniciusgerevini/godot-aseprite-wizard (star 1396) | License: MIT | Collected: 2026-10-29
# Commit:  18ebea9868ea
@tool
extends EditorInspectorPlugin

const ASInspectorDock = preload("./animated_sprite_inspector_dock.tscn")

func _can_handle(object):
	return object is AnimatedSprite2D || object is AnimatedSprite3D


func _parse_end(object):
	var dock = ASInspectorDock.instantiate()
	dock.target_node = object
	add_custom_control(dock)
