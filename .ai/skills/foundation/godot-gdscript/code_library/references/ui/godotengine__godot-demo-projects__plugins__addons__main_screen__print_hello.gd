# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/plugins/addons/main_screen/print_hello.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
@tool
extends Button


func _on_PrintHello_pressed() -> void:
	print("Hello from the main screen plugin!")
