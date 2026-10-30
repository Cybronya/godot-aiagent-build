# Source:  https://github.com/Maran23/script-ide/blob/master/addons/script-ide/outline/outline_button.gd
# Repo:    Maran23/script-ide (star 1059) | License: MIT | Collected: 2026-10-29
# Commit:  c1dfb1f0b94e
## Button that is used as in the outline for a concrete outline type.
@tool
extends Button

signal right_clicked

func _init() -> void:
	toggle_mode = true
	icon_alignment = HORIZONTAL_ALIGNMENT_CENTER

	add_theme_stylebox_override(&"normal", StyleBoxEmpty.new())

	add_theme_color_override(&"icon_pressed_color", Color.WHITE)
	add_theme_color_override(&"icon_hover_color", Color.WHITE)
	add_theme_color_override(&"icon_hover_pressed_color", Color.WHITE)
	add_theme_color_override(&"icon_focus_color", Color.WHITE)

func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton && event.pressed:
		if (event.button_index == MOUSE_BUTTON_RIGHT):
			button_pressed = true
			on_right_click()

func on_right_click() -> void:
	right_clicked.emit()
