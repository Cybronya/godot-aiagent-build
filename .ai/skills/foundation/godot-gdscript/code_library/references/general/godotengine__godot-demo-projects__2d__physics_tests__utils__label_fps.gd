# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/physics_tests/utils/label_fps.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends Label

func _process(_delta: float) -> void:
	text = "%d FPS (%.2f mspf)" % [Engine.get_frames_per_second(), 1000.0 / Engine.get_frames_per_second()]
