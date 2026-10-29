# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/about/module.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  863324dfb752
class_name PankuModuleAbout extends PankuModule

var window:PankuLynxWindow
const ui = preload("./about.tscn")

func open_window():
	if window: return
	var ui_instance = ui.instantiate()
	ui_instance._module = self
	window = core.windows_manager.create_window(ui_instance)
	window.set_window_title_text("About")
	window.show_window()
	window.window_closed.connect(
		func(): window = null
	)
