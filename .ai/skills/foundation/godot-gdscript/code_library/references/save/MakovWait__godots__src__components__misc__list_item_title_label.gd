# Source:  https://github.com/MakovWait/godots/blob/main/src/components/misc/list_item_title_label.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
extends Label


func _ready() -> void:
	clip_text = true
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	custom_minimum_size = Vector2(128, 0) * Config.EDSCALE
	add_theme_font_override(
		"font", get_theme_font("title", "EditorFonts")
	)
	add_theme_font_size_override(
		"font_size", get_theme_font_size("title_size", "EditorFonts")
	)
	add_theme_color_override(
		"font_color",
		get_theme_color("font_color", "Tree")
	)
