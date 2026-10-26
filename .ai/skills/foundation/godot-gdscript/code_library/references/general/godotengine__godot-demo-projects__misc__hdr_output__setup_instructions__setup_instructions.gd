# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/misc/hdr_output/setup_instructions/setup_instructions.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends RichTextLabel


func _on_meta_clicked(meta: Variant) -> void:
	OS.shell_open(str(meta))
