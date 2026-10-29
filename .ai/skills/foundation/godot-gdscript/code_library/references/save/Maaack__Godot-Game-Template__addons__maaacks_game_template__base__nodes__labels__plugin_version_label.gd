# Source:  https://github.com/Maaack/Godot-Game-Template/blob/main/addons/maaacks_game_template/base/nodes/labels/plugin_version_label.gd
# Repo:    Maaack/Godot-Game-Template (star 1709) | License: MIT | Collected: 2026-10-26
# Commit:  5cc611f7dfcd
@tool
extends Label
## Displays the value of `version` from the config file of the specified plugin.

const NO_VERSION_STRING : String = "0.0.0"

@export var plugin_directory : String
@export var version_prefix : String = "v"

func _get_plugin_version() -> String:
	if not plugin_directory.is_empty():
		for enabled_plugin in ProjectSettings.get_setting("editor_plugins/enabled"):
			if enabled_plugin.contains(plugin_directory):
				var config := ConfigFile.new()
				var error = config.load(enabled_plugin)
				if error != OK:
					break
				return config.get_value("plugin", "version", NO_VERSION_STRING)
	return ""

func update_version_label() -> void:
	var plugin_version = _get_plugin_version()
	if plugin_version.is_empty():
		plugin_version = NO_VERSION_STRING
	text = version_prefix + plugin_version

func _ready() -> void:
	update_version_label()
