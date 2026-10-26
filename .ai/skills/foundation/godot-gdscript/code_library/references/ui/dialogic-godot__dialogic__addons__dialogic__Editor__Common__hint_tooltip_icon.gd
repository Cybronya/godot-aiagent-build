# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Editor/Common/hint_tooltip_icon.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  main
@tool
extends TextureRect

@export_multiline var hint_text := ""

func _ready() -> void:
	if owner and owner.get_parent() is SubViewport:
		texture = null
		return
	texture = get_theme_icon("NodeInfo", "EditorIcons")
	modulate = get_theme_color("contrast_color_1", "Editor")
	tooltip_text = hint_text
