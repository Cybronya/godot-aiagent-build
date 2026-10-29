# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/history_manager/module.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  863324dfb752
class_name PankuModuleHistoryManager extends PankuModule

var window:PankuLynxWindow

func init_module():
	# setup ui
	var ui = preload("./exp_history.tscn").instantiate()
	ui.console = core
	core.new_expression_entered.connect(
		func(expression, result):
			ui.add_history(expression)
	)

	# bind window
	window = core.windows_manager.create_window(ui)
	add_auto_save_hook(window)
	window.queue_free_on_close = false
	window.set_window_title_text("History Manager")
	load_window_data(window)

func quit_module():
	super.quit_module()
	save_window_data(window)

func open_window():
	window.show_window()
