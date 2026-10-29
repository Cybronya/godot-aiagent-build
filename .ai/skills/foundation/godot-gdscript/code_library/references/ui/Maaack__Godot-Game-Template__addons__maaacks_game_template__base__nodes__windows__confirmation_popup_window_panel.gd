# Source:  https://github.com/Maaack/Godot-Game-Template/blob/main/addons/maaacks_game_template/base/nodes/windows/confirmation_popup_window_panel.gd
# Repo:    Maaack/Godot-Game-Template (star 1709) | License: MIT | Collected: 2026-10-26
# Commit:  5cc611f7dfcd
@tool
class_name ConfirmationPopupWindowPanel
extends PopupWindowPanel

signal confirmed

## Text to use for the confirm button.
@export var confirm_button_text : String = "Confirm" :
	set(value):
		confirm_button_text = value
		if update_content and is_inside_tree():
			confirm_button.text = confirm_button_text

@onready var confirm_button : Button = %ConfirmButton

func _ready() -> void:
	super._ready()
	if not confirm_button.pressed.is_connected(_on_confirm_button_pressed):
		confirm_button.pressed.connect(_on_confirm_button_pressed)

func confirm():
	confirmed.emit()
	close()

func _on_confirm_button_pressed():
	confirm()
