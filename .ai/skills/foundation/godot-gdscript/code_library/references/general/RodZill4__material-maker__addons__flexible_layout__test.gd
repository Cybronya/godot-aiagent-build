# Source:  https://github.com/RodZill4/material-maker/blob/master/addons/flexible_layout/test.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
extends Control

func _ready():
	get_window().borderless = false
	get_window().size = Vector2i(1024, 768)
	#await get_tree().process_frame
	var file : FileAccess = FileAccess.open("res://addons/flexible_layout/layout.json", FileAccess.READ)
	if file:
		var layout = JSON.parse_string(file.get_as_text())
		$FlexibleLayout.init(layout as Dictionary if layout else null)

func _on_tree_exiting():
	var file : FileAccess = FileAccess.open("res://addons/flexible_layout/layout.json", FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify($FlexibleLayout.serialize()))
		
