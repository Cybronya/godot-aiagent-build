# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/plugins/addons/simple_import_plugin/plugin.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
@tool
extends EditorPlugin

var import_plugin: EditorImportPlugin


func _enter_tree() -> void:
	import_plugin = preload("import.gd").new()
	add_import_plugin(import_plugin)


func _exit_tree() -> void:
	remove_import_plugin(import_plugin)
	import_plugin = null
