# Source:  https://github.com/dreadpon/godot_spatial_gardener/blob/master/addons/dreadpon.spatial_gardener/utility/console/console_input_field.gd
# Repo:    dreadpon/godot_spatial_gardener (star 1319) | License: MIT | Collected: 2026-10-29
# Commit:  77b822f50ded
@tool
extends TextEdit




func _process(delta):
	if visible:
		call_deferred("_hide_scrollbar")


func _hide_scrollbar():
	for child in get_children():
		if is_instance_of(child, VScrollBar):
			child.visible = false
		elif is_instance_of(child, HScrollBar):
			child.visible = false
