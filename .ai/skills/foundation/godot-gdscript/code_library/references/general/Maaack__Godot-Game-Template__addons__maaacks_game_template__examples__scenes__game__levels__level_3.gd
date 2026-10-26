# Source:  https://github.com/Maaack/Godot-Game-Template/blob/main/addons/maaacks_game_template/examples/scenes/game/levels/level_3.gd
# Repo:    Maaack/Godot-Game-Template (star 1709) | License: MIT | Collected: 2026-10-26
# Commit:  main
extends "level.gd"

func _on_lose_area_3d_body_entered(_body: Node3D) -> void:
	level_lost.emit()

func _on_win_area_3d_body_entered(_body: Node3D) -> void:
	level_won.emit(next_level_path)
