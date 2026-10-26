# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/3d/variable_rate_shading/information.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends VBoxContainer


func _ready() -> void:
	get_viewport().size_changed.connect(_on_viewport_size_changed)
	_on_viewport_size_changed()


func _process(_delta: float) -> void:
	$FPS.text = "%d FPS (%.2f mspf)" % [Engine.get_frames_per_second(), 1000.0 / Engine.get_frames_per_second()]


func _on_viewport_size_changed() -> void:
	$Resolution.text = "%s × %s" % [get_viewport().size.x, get_viewport().size.y]
