# Source:  https://github.com/OctoD/godot-gameplay-systems/blob/main/addons/godot_gameplay_systems/camera_shake/plugin.gd
# Repo:    OctoD/godot-gameplay-systems (star 746) | License: MIT | Collected: 2026-10-31
# Commit:  9349931cc7a5
@tool
extends EditorPlugin


func _enter_tree() -> void:
	add_custom_type("CameraShake", "Node", preload("./nodes/camera_shake.gd"), null)


func _exit_tree() -> void:
	remove_custom_type("CameraShake")
