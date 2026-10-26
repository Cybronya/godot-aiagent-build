# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/misc/multiple_windows/scenes/window/url_opener.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends RichTextLabel


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	meta_clicked.connect(_on_meta_clicked)


func _on_meta_clicked(meta: Variant) -> void:
	OS.shell_open(str(meta))
