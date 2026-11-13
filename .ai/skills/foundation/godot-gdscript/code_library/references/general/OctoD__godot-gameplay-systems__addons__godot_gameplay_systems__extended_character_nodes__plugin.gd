# Source:  https://github.com/OctoD/godot-gameplay-systems/blob/main/addons/godot_gameplay_systems/extended_character_nodes/plugin.gd
# Repo:    OctoD/godot-gameplay-systems (star 746) | License: MIT | Collected: 2026-10-31
# Commit:  9349931cc7a5
extends EditorPlugin


func _enter_tree() -> void:
	add_custom_type("PointAndClick2D", "Node2D", preload("./nodes/2d/point_and_click_2d.gd"), null)
	add_custom_type("PointAndClick3D", "Node3D", preload("./nodes/3d/point_and_click_3d.gd"), null)


func _exit_tree() -> void:
	remove_custom_type("PointAndClick2D")
	remove_custom_type("PointAndClick3D")

	