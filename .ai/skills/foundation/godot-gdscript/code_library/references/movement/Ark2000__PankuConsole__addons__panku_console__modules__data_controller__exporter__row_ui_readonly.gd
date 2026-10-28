# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/data_controller/exporter/row_ui_readonly.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends "./row_ui.gd"

@export var ledit:LineEdit

func update_ui(val):
	ledit.text = str(val)
