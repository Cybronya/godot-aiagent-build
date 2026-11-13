# Source:  https://github.com/OctoD/godot-gameplay-systems/blob/main/addons/godot_gameplay_systems/slideshow/plugin.gd
# Repo:    OctoD/godot-gameplay-systems (star 746) | License: MIT | Collected: 2026-10-31
# Commit:  9349931cc7a5
extends EditorPlugin


const slideshow_script = preload("./slide_show.gd")


func _enter_tree() -> void:
	add_custom_type("SlideShow", "Node2D", slideshow_script, null)
	
	
func _exit_tree() -> void:
	remove_custom_type("SlideShow")

