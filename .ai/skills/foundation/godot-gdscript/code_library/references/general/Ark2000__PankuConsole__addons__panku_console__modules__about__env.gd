# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/about/env.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  863324dfb752
var _module:PankuModule

const _HELP_open = "Open about window"
func open() -> void:
	_module.open_window()
