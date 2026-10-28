# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/keyboard_shortcuts/opt.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends ModuleOptions

@export_group("keyboard_shortcuts")

@export var export_button_open_keyboard_shortcuts := "Open Keyboard Shortcuts"

func open_keyboard_shortcuts():
	_module.open_window()
