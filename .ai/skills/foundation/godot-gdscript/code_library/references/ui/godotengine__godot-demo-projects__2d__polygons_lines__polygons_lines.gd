# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/polygons_lines/polygons_lines.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Node2D


func _ready() -> void:
	if RenderingServer.get_current_rendering_method() == "gl_compatibility":
		$MSAA.visible = false
		$UnsupportedLabel.visible = true


func _on_msaa_option_button_item_selected(index: int) -> void:
	get_viewport().msaa_2d = index as Viewport.MSAA
