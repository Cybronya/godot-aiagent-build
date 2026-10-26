# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/platformer/touch_screen_ui.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends CanvasLayer


func _ready() -> void:
	hide()
	if DisplayServer.is_touchscreen_available():
		show()
