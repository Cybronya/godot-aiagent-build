# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/system_report/env.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  master
var _os_report = preload("./os_report.gd").new()
var _module:PankuModule

const _HELP_execute = "Show detailed OS report"
func execute() -> String:
	_module.core.notify("Please wait, this may take a while...")
	_os_report.inspect()
	var report =  "".join(_os_report.rtl)
	return report
