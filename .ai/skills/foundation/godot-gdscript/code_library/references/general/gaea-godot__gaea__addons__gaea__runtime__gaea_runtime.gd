# Source:  https://github.com/gaea-godot/gaea/blob/2.0/addons/gaea/runtime/gaea_runtime.gd
# Repo:    gaea-godot/gaea (star 1663) | License: MIT | Collected: 2026-10-28
# Commit:  2.0
@tool
extends EditorPlugin


var _custom_project_settings: GaeaProjectSettings


func _enter_tree() -> void:
	_custom_project_settings = GaeaProjectSettings.new()
	_custom_project_settings.add_settings()


func _exit_tree() -> void:
	_custom_project_settings.remove_settings()
