# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/nodes/node_button.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends TextureButton

signal on_show_popup()

func _on_gui_input(event):
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_RIGHT:
		on_show_popup.emit()
