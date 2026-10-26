# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Modules/Wait/index.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  main
@tool
extends DialogicIndexer


func _get_events() -> Array:
	return [this_folder.path_join('event_wait.gd')]


func _get_subsystems() -> Array:
	return [{'name':'Wait', 'script':this_folder.path_join('subsystem_wait.gd')}]
