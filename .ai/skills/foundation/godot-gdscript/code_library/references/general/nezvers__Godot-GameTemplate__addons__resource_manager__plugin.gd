# Source:  https://github.com/nezvers/Godot-GameTemplate/blob/master/addons/resource_manager/plugin.gd
# Repo:    nezvers/Godot-GameTemplate (star 1670) | License: MIT | Collected: 2026-10-26
# Commit:  d5d8d1588742
@tool
extends EditorPlugin

const MANAGER_PANEL = preload("res://addons/resource_manager/scenes/manager_panel.tscn")

var manager_panel:ResourceManagerPanel

func _enter_tree() -> void:
	manager_panel = MANAGER_PANEL.instantiate()
	manager_panel.is_tool = true
	manager_panel.name = "Resource Manager"
	
	add_control_to_dock(EditorPlugin.DOCK_SLOT_LEFT_UR, manager_panel)


func _exit_tree() -> void:
	remove_control_from_docks(manager_panel)
	manager_panel.queue_free()
