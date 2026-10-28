# Source:  https://github.com/HungryProton/scatter/blob/main/addons/proton_scatter/src/stack/inspector_plugin/editor_property.gd
# Repo:    HungryProton/scatter (star 3017) | License: MIT | Collected: 2026-10-28
# Commit:  main
@tool
extends EditorProperty


var _ui: Control


func _init():
	_ui = preload("./ui/stack_panel.tscn").instantiate()
	add_child(_ui)
	set_bottom_editor(_ui)


func set_node(object) -> void:
	_ui.set_node(object)
