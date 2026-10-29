# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/physics_tests/utils/label_frames.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Label

var _unpaused_frame_count: int = 0


func reset() -> void:
	_unpaused_frame_count = 0
	text = "%d Frames" % [_unpaused_frame_count]


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_PAUSABLE


func _process(_delta: float) -> void:
	text = "%d Frames" % [_unpaused_frame_count]


func _physics_process(_delta: float) -> void:
	_unpaused_frame_count += 1
