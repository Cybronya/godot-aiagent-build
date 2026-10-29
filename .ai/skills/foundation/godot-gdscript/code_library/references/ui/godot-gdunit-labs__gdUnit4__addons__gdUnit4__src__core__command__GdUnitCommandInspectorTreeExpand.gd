# Source:  https://github.com/godot-gdunit-labs/gdUnit4/blob/master/addons/gdUnit4/src/core/command/GdUnitCommandInspectorTreeExpand.gd
# Repo:    godot-gdunit-labs/gdUnit4 (star 1283) | License: MIT | Collected: 2026-10-29
# Commit:  e031bd413681
class_name GdUnitCommandInspectorTreeExpand
extends GdUnitBaseCommand

const GdUnitInspectorTreeMainPanel := preload("res://addons/gdUnit4/src/ui/parts/GdUnitInspectorTreeMainPanel.gd")
const ID := "Inspector Tree Expand"


func _init() -> void:
	super(ID, GdUnitShortcut.ShortCut.NONE)
	icon = GdUnitUiTools.get_icon("ExpandTree")


func execute(..._parameters: Array) -> void:
	var inspector: GdUnitInspectorTreeMainPanel = EditorInterface.get_base_control().get_meta("GdUnit4Inspector")
	var selected_item := inspector._tree.get_selected()
	if selected_item == null:
		selected_item = inspector._tree.get_root()
	else:
		selected_item = selected_item.get_parent()

	inspector.do_collapse_all(false, selected_item)


func _do_stop() -> void:
	pass
