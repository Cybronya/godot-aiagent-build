# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/export_plugin.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  701b67bbe601
extends EditorExportPlugin


const IGNORED_PATHS = [
	"/Editor", 
	"/Modules", 
	"/Example Assets/portraits"
]


func _get_name() -> String:
	return "Dialogic Export Plugin"


func _export_file(path: String, type: String, features: PackedStringArray) -> void:
	var plugin_path: String = "res://addons/dialogic"
	
	for ignored_path: String in IGNORED_PATHS:
		if path.begins_with(plugin_path + ignored_path):
			if path.ends_with(".png"):
				skip()
			elif path.ends_with(".tff"):
				skip()
