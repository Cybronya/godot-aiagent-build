# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/interactive_shell/env.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  863324dfb752
var _module:PankuModule

func open_window(): _module.open_window()

func open_launcher(): _module.open_launcher()

func set_unified_window_visibility(enabled:bool):
	_module.set_unified_window_visibility(enabled)

func set_pause_if_popup(enabled:bool):
	_module.set_pause_if_popup(enabled)
