# Source:  https://github.com/MakovWait/godots/blob/main/src/components/misc/list_item_path_label.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
extends Label


func _ready() -> void:
	add_theme_color_override(
		"font_color",
		get_theme_color("font_color", "Tree")
	)
	clip_text = true
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	structured_text_bidi_override = TextServer.STRUCTURED_TEXT_FILE
