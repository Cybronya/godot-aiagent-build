# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/visibility_ranges/fps_label.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Label


func _process(_delta: float) -> void:
	var fps: float = Engine.get_frames_per_second()
	text = "%d FPS (%.2f mspf)" % [fps, 1000.0 / fps]
