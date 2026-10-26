# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Modules/TextInput/index.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  main
@tool
extends DialogicIndexer


func _get_events() -> Array:
	return [this_folder.path_join('event_text_input.gd')]


func _get_subsystems() -> Array:
	return [{'name':'TextInput', 'script':this_folder.path_join('subsystem_text_input.gd')}]

