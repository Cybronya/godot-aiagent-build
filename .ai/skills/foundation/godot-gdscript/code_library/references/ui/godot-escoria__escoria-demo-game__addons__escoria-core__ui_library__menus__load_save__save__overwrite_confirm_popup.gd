# Source:  https://github.com/godot-escoria/escoria-demo-game/blob/main/addons/escoria-core/ui_library/menus/load_save/save/overwrite_confirm_popup.gd
# Repo:    godot-escoria/escoria-demo-game (star 855) | License: MIT | Collected: 2026-10-29
# Commit:  92e650697717
extends Popup

signal confirm_yes

func _ready():
	$MarginContainer/VBoxContainer/HBoxContainer/yes.grab_focus()

func _on_no_pressed():
	hide()


func _on_yes_pressed():
	confirm_yes.emit()
	hide()
