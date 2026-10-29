# Source:  https://github.com/dreadpon/godot_spatial_gardener/blob/master/addons/dreadpon.spatial_gardener/controls/extensions/lose_focus_control.gd
# Repo:    dreadpon/godot_spatial_gardener (star 1319) | License: MIT | Collected: 2026-10-29
# Commit:  77b822f50ded
@tool
extends LineEdit



# Release focus from a child node when pressing enter
func _gui_input(event):
	if has_focus():
		if is_instance_of(event, InputEventKey) && !event.pressed:
			if event.keycode == KEY_ENTER || event.keycode == KEY_KP_ENTER || event.keycode == KEY_ESCAPE:
				release_focus()
				if is_instance_of(self, LineEdit):
					caret_column = 0
