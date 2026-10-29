# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/interactive_shell/console_ui/remote_control_node.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  863324dfb752
extends Control

@export
var target_control:Control

func _ready():
	if not target_control:
		return
		
	target_control.resized.connect(
		func():
			custom_minimum_size = target_control.get_minimum_size()
	)
	
	target_control.resized.emit()
