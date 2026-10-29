# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/check_latest_release/opt.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  863324dfb752
extends ModuleOptions

@export_group("check_latest_release")

@export var export_button_check_update := "Check Update"

func check_update():
	_module.check()
