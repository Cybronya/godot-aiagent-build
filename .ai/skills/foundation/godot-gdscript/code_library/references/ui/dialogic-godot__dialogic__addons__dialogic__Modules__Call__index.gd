# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Modules/Call/index.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  701b67bbe601
@tool
extends DialogicIndexer


func _get_events() -> Array:
	return [this_folder.path_join('event_call.gd')]
