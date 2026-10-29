# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/data_controller/exporter/row_ui_enum.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  863324dfb752
extends "./row_ui.gd"

@export var opt_btn:OptionButton

func update_ui(val):
	opt_btn.select(val)

func is_active():
	return opt_btn.has_focus()

func _ready():
	opt_btn.item_selected.connect(
		func(index:int):
			ui_val_changed.emit(index)
	)
	
	# wtf, transparent background is a mess
	var popup := opt_btn.get_popup()
	popup.transparent_bg = true
	popup.transparent = true

func setup(params := []):
	opt_btn.clear()
	for p in params:
		opt_btn.add_item(p)
