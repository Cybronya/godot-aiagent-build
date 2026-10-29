# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/windows/node_editor/node_editor_item_list.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
extends VBoxContainer

func update_up_down_buttons() -> void:
	for c in get_children():
		if ! (c is Button):
			c.update_up_down_button()
