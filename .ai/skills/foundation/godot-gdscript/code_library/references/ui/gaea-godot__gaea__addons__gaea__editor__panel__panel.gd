# Source:  https://github.com/gaea-godot/gaea/blob/2.0/addons/gaea/editor/panel/panel.gd
# Repo:    gaea-godot/gaea (star 1663) | License: MIT | Collected: 2026-10-28
# Commit:  2.0
@tool
class_name GaeaEditorPanel
extends Control


@export var main_view: GaeaEditorMainView
@export var graph_edit: GaeaEditorGraphEdit
@export var file_list: GaeaEditorFileList
@export var preview_panel: GaeaEditorPreviewPanel

var plugin: GaeaEditorPlugin

static func instantiate() -> Node:
	return load("uid://dngytsjlmkfg7").instantiate()


func _ready() -> void:
	if is_part_of_edited_scene():
		return
