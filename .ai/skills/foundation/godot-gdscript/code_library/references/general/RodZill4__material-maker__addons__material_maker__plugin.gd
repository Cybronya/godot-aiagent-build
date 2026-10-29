# Source:  https://github.com/RodZill4/material-maker/blob/master/addons/material_maker/plugin.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
@tool
extends EditorPlugin

var importer = null

func _enter_tree() -> void:
	importer = preload("res://addons/material_maker/import_plugin/ptex_import.gd").new(self)
	add_import_plugin(importer)

func _exit_tree() -> void:
	if importer != null:
		remove_import_plugin(importer)
		importer = null
