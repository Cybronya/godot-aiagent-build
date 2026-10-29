# Source:  https://github.com/dreadpon/godot_spatial_gardener/blob/master/addons/dreadpon.spatial_gardener/utility/console/console_output.gd
# Repo:    dreadpon/godot_spatial_gardener (star 1319) | License: MIT | Collected: 2026-10-29
# Commit:  77b822f50ded
@tool
extends RichTextLabel


@export var scrollbar_size = 24

func _ready():
	for child in get_children():
		if is_instance_of(child, VScrollBar):
			child.custom_minimum_size.x = scrollbar_size
		elif is_instance_of(child, HScrollBar):
			child.custom_minimum_size.y = scrollbar_size
