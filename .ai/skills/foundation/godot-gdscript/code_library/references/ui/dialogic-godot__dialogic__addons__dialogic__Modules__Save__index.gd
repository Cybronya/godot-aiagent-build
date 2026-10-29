# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Modules/Save/index.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  701b67bbe601
@tool
extends DialogicIndexer


func _get_events() -> Array:
	return [this_folder.path_join('event_save.gd')]


func _get_subsystems() -> Array:
	return [{'name':'Save', 'script':this_folder.path_join('subsystem_save.gd')}]


func _get_settings_pages() -> Array:
	return [this_folder.path_join('settings_save.tscn')]
