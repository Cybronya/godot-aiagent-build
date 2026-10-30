# Source:  https://github.com/crystal-bit/godot-game-template/blob/main/addons/ggt-core/plugin.gd
# Repo:    crystal-bit/godot-game-template (star 993) | License: MIT | Collected: 2026-10-29
# Commit:  e9dc8926d156
@tool
extends EditorPlugin


func _enter_tree():
	pass


func _enable_plugin():
	add_autoload_singleton("GGT", "res://addons/ggt-core/ggt.gd")
	add_autoload_singleton("GGT_GameConfig", "res://addons/ggt-core/autoload/game_settings_config.gd")


func _exit_tree():
	pass


func _disable_plugin():
	remove_autoload_singleton("GGT")
	remove_autoload_singleton("GGT_GameConfig")
