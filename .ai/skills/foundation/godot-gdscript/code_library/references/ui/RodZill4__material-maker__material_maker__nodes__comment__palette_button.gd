# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/nodes/comment/palette_button.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends ColorRect

signal pressed(color)

func _ready() -> void:
	connect("gui_input", Callable(self, "_on_gui_input"))

func _on_gui_input(event) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		emit_signal("pressed", color)
