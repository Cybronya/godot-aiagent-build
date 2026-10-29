# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/physics_tests/utils/label_version.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Label

func _ready() -> void:
	text = "Godot Version: %s" % Engine.get_version_info().string
