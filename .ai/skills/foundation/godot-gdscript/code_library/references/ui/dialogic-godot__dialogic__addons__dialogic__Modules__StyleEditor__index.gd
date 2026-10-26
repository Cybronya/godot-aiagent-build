# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Modules/StyleEditor/index.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  main
@tool
extends DialogicIndexer

func _get_editors() -> Array:
	return [this_folder.path_join('style_editor.tscn')]
