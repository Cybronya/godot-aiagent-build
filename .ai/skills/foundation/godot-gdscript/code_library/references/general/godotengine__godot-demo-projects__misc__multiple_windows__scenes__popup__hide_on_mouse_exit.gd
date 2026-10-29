# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/misc/multiple_windows/scenes/popup/hide_on_mouse_exit.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Popup


func _ready() -> void:
	mouse_exited.connect(_on_mouse_exited)


func _on_mouse_exited():
	hide()
