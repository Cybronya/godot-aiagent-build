# Source:  https://github.com/MewPurPur/GodSVG/blob/main/no_export/scripts/generate_theme.gd
# Repo:    MewPurPur/GodSVG (star 2784) | License: MIT | Collected: 2026-10-28
# Commit:  52ad7944fcf9
# Run with Ctrl+Shift+X.
# A script intended to generate a theme for temporary testing in the editor.
# Make sure to delete it after.
@tool
extends EditorScript

func _run() -> void:
	var theme := ThemeUtils.generate_theme()
	ResourceSaver.save(theme, "res://no_export/temp_theme.tres")
	print("Theme updated.")
