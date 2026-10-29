# Source:  https://github.com/viniciusgerevini/godot-aseprite-wizard/blob/godot_4/addons/AsepriteWizard/interface/shared/tree/tree_selection_confirmation_warning.gd
# Repo:    viniciusgerevini/godot-aseprite-wizard (star 1396) | License: MIT | Collected: 2026-10-29
# Commit:  18ebea9868ea
@tool
extends VBoxContainer

signal warning_confirmed
signal warning_declined

@onready var _warning_message = $MarginContainer/warning_message

func set_message(text: String) -> void:
	_warning_message.text = text


func _on_confirm_button_up():
	warning_confirmed.emit()


func _on_cancel_button_up():
	warning_declined.emit()
