# Source:  https://github.com/nathanhoad/godot_sound_manager/blob/main/addons/sound_manager/plugin.gd
# Repo:    nathanhoad/godot_sound_manager (star 830) | License: MIT | Collected: 2026-10-31
# Commit:  1c041582db80
@tool
extends EditorPlugin


func _enter_tree() -> void:
	add_autoload_singleton("SoundManager", get_plugin_path() + "/sound_manager.gd")


func _exit_tree() -> void:
	remove_autoload_singleton("SoundManager")


func get_plugin_path() -> String:
	return get_script().resource_path.get_base_dir()
