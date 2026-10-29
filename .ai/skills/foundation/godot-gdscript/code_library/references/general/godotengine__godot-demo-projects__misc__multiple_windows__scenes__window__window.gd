# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/misc/multiple_windows/scenes/window/window.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Window


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	close_requested.connect(_on_close_requested)


func _on_close_requested() -> void:
	print("%s %s was hidden." % [str(get_class()), name])
	hide()
