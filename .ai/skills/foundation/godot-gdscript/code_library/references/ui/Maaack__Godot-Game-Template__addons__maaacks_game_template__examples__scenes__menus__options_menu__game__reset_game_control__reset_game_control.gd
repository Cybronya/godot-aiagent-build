# Source:  https://github.com/Maaack/Godot-Game-Template/blob/main/addons/maaacks_game_template/examples/scenes/menus/options_menu/game/reset_game_control/reset_game_control.gd
# Repo:    Maaack/Godot-Game-Template (star 1709) | License: MIT | Collected: 2026-10-26
# Commit:  5cc611f7dfcd
extends HBoxContainer

const RESET_STRING := "Reset Game:"
const CONFIRM_STRING := "Confirm Reset:"

signal reset_confirmed

func _on_cancel_button_pressed():
	%CancelButton.hide()
	%ConfirmButton.hide()
	%ResetButton.show()
	%ResetButton.grab_focus()
	%ResetLabel.text = RESET_STRING

func _on_reset_button_pressed():
	%CancelButton.show()
	%ConfirmButton.show()
	%CancelButton.grab_focus()
	%ResetButton.hide()
	%ResetLabel.text = CONFIRM_STRING

func _on_confirm_button_pressed():
	reset_confirmed.emit()
	get_tree().paused = false
	get_tree().reload_current_scene()
