# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/networking/webrtc_minimal/link_button.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends LinkButton

func _on_LinkButton_pressed() -> void:
	OS.shell_open("https://github.com/godotengine/webrtc-native/releases")
