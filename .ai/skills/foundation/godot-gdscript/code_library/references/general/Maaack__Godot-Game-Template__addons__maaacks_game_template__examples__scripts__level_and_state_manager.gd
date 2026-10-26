# Source:  https://github.com/Maaack/Godot-Game-Template/blob/main/addons/maaacks_game_template/examples/scripts/level_and_state_manager.gd
# Repo:    Maaack/Godot-Game-Template (star 1709) | License: MIT | Collected: 2026-10-26
# Commit:  main
extends LevelManager

func set_current_level_path(value : String) -> void:
	super.set_current_level_path(value)
	GameStateExample.set_current_level_path(value)

func set_checkpoint_level_path(value : String) -> void:
	super.set_checkpoint_level_path(value)
	GameStateExample.set_checkpoint_level_path(value)

func get_checkpoint_level_path() -> String:
	var state_level_path := GameStateExample.get_checkpoint_level_path()
	if not state_level_path.is_empty():
		return state_level_path
	return super.get_checkpoint_level_path()
