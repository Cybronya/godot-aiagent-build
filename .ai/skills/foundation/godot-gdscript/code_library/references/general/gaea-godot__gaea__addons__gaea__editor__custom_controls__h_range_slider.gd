# Source:  https://github.com/gaea-godot/gaea/blob/2.0/addons/gaea/editor/custom_controls/h_range_slider.gd
# Repo:    gaea-godot/gaea (star 1663) | License: MIT | Collected: 2026-10-28
# Commit:  2.0
@tool
class_name GaeaEditorHRangeSlider
extends GaeaEditorRangeSlider

## A horizontal [RangeSlider] that goes from left ([member min_value]) to right ([member max_value]),
## used to adjust a range by moving grabbers along a horizontal axis.


func _init() -> void:
	_orientation = Orientation.HORIZONTAL
	super()
