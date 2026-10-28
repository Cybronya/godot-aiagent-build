# Source:  https://github.com/gaea-godot/gaea/blob/2.0/addons/gaea/editor/export.gd
# Repo:    gaea-godot/gaea (star 1663) | License: MIT | Collected: 2026-10-28
# Commit:  2.0
@tool

class_name GaeaEditorExportPlugin
extends EditorExportPlugin


func _get_name() -> String:
	# The name should be < "GDScript" or the skips won't works.
	# See https://github.com/godotengine/godot/issues/93487.
	# Docs: "The plugins are sorted by name before exporting".
	return "GDA_Gaea"


func _export_file(path: String, _type: String, _features: PackedStringArray) -> void:
	if path.begins_with("res://addons/gaea/editor/"):
		skip()
		return
