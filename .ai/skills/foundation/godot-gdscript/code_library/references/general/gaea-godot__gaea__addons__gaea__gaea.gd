# Source:  https://github.com/gaea-godot/gaea/blob/2.0/addons/gaea/gaea.gd
# Repo:    gaea-godot/gaea (star 1663) | License: MIT | Collected: 2026-10-28
# Commit:  2.0
@tool
extends EditorPlugin


func _enable_plugin() -> void:
	if Engine.is_editor_hint():
		EditorInterface.set_plugin_enabled("gaea/editor", true)
		EditorInterface.set_plugin_enabled("gaea/runtime", true)


func _disable_plugin() -> void:
	if Engine.is_editor_hint():
		EditorInterface.set_plugin_enabled("gaea/editor", false)
		EditorInterface.set_plugin_enabled("gaea/runtime", false)
