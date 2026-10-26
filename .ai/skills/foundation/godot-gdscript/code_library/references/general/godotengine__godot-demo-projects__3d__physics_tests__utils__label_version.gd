# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/physics_tests/utils/label_version.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Label


func _process(_delta: float) -> void:
	set_text("Godot Version: %s" % Engine.get_version_info().string)
