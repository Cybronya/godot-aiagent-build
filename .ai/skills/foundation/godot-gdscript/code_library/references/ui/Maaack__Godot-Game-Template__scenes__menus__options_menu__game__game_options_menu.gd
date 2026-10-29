# Source:  https://github.com/Maaack/Godot-Game-Template/blob/main/scenes/menus/options_menu/game/game_options_menu.gd
# Repo:    Maaack/Godot-Game-Template (star 1709) | License: MIT | Collected: 2026-10-26
# Commit:  5cc611f7dfcd
extends Control

func _on_ResetGameControl_reset_confirmed() -> void:
	GameState.reset()
