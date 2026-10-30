# Source:  https://github.com/crystal-bit/godot-game-template/blob/main/addons/ggt-core/settings/confirmation_modal.gd
# Repo:    crystal-bit/godot-game-template (star 993) | License: MIT | Collected: 2026-10-29
# Commit:  e9dc8926d156
extends Control
class_name ConfirmationModal

signal confirmed
signal cancelled

@export var label: Label
@export var confirm_button: Button
@export var cancel_button: Button

func _ready() -> void:
	confirm_button.pressed.connect(_on_confirm_pressed)
	cancel_button.pressed.connect(_on_cancel_pressed)
	hide()


func show_with_text(text: String) -> void:
	label.text = text
	show()
	confirm_button.grab_focus()


func _on_confirm_pressed() -> void:
	confirmed.emit()
	hide()


func _on_cancel_pressed() -> void:
	cancelled.emit()
	hide()
