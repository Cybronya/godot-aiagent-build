# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/history_manager/opt.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  863324dfb752
extends ModuleOptions

@export_group("history_manager")

@export var export_button_open_window := "Open Window"
func open_window():
	_module.open_window()
