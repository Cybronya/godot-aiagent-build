# Source:  https://github.com/Maaack/Godot-Game-Template/blob/main/addons/maaacks_music_controller/class.gd
# Repo:    Maaack/Godot-Game-Template (star 1709) | License: MIT | Collected: 2026-10-26
# Commit:  5cc611f7dfcd
@tool
class_name MaaacksMusicController
extends RefCounted

const PLUGIN_NAME = "Maaack's Music Controller"
const PROJECT_SETTINGS_PATH = "maaacks_music_controller/"

static func get_plugin_name() -> String:
	return PLUGIN_NAME

static func get_settings_path() -> String:
	return PROJECT_SETTINGS_PATH
