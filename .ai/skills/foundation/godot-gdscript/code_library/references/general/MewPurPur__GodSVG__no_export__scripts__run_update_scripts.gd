# Source:  https://github.com/MewPurPur/GodSVG/blob/main/no_export/scripts/run_update_scripts.gd
# Repo:    MewPurPur/GodSVG (star 2784) | License: MIT | Collected: 2026-10-28
# Commit:  main
# Run with Ctrl+Shift+X.
@tool
extends EditorScript

func _run() -> void:
	for path in ["res://no_export/scripts/update_translations.gd", "res://no_export/scripts/update_desktop_file.gd"]:
		load(path).new()._run()
