# Source:  https://github.com/Maaack/Godot-Game-Template/blob/main/addons/maaacks_game_template/examples/scenes/game/levels/level_1.gd
# Repo:    Maaack/Godot-Game-Template (star 1709) | License: MIT | Collected: 2026-10-26
# Commit:  5cc611f7dfcd
extends "level.gd"

func _on_lose_button_pressed() -> void:
	level_lost.emit()

func _on_win_button_pressed() -> void:
	level_won.emit(next_level_path)

func _ready() -> void:
	super._ready()
	%ColorPickerButton.color = level_state.color
	%BackgroundColor.color = level_state.color

func _on_color_picker_button_color_changed(color : Color) -> void:
	%BackgroundColor.color = color
	level_state.color = color
	GlobalState.save()
