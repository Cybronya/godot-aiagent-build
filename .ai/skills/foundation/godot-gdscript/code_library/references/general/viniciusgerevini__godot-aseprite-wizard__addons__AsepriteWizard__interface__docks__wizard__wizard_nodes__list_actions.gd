# Source:  https://github.com/viniciusgerevini/godot-aseprite-wizard/blob/godot_4/addons/AsepriteWizard/interface/docks/wizard/wizard_nodes/list_actions.gd
# Repo:    viniciusgerevini/godot-aseprite-wizard (star 1396) | License: MIT | Collected: 2026-10-29
# Commit:  18ebea9868ea
@tool
extends HBoxContainer

signal import_clicked(index)
signal edit_clicked(index)
signal removed_clicked(index)

var history_index = -1


func _on_edit_pressed():
	emit_signal("edit_clicked", history_index)


func _on_reimport_pressed():
	emit_signal("import_clicked", history_index)


func _on_remove_pressed():
	emit_signal("removed_clicked", history_index)
