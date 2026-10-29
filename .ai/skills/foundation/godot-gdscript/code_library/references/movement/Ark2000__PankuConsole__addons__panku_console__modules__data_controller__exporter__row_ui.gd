# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/data_controller/exporter/row_ui.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  863324dfb752
extends HBoxContainer

var name_label:Label:
	get: return get_node("VName")

signal ui_val_changed(val)

func get_ui_val() -> Variant:
	return null

func update_ui(val):
	pass

#stop sync if is active(eg. a line edit node is in focus)
func is_active() -> bool:
	return false
