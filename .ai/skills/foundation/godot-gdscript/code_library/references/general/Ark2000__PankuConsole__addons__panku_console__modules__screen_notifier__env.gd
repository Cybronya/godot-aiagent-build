# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/screen_notifier/env.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  master
var _module:PankuModule

const _HELP_notify = "Generate a notification"
func notify(any):
	_module.notify(str(any))
