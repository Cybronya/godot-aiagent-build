# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Modules/HighlightPortrait/index.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  701b67bbe601
@tool
extends DialogicIndexer


func _get_portrait_scene_presets() -> Array[Dictionary]:
	return [
		{
			"path": this_folder.path_join("simple_highlight_portrait.tscn"),
			"name": "Simple Highlight Portrait",
			"description": "A portrait scene that displays a simple image, but changes color and moves to the front when this character is speaking.",
			"author":"Dialogic",
			"type": "General",
			"icon":"",
			"preview_image":[this_folder.path_join("highlight_portrait_thumbnail.png")],
			"documentation":"",
		},
	]
