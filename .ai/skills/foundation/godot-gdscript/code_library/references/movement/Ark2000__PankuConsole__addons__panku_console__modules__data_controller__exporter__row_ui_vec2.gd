# Source:  https://github.com/Ark2000/PankuConsole/blob/master/addons/panku_console/modules/data_controller/exporter/row_ui_vec2.gd
# Repo:    Ark2000/PankuConsole (star 1436) | License: MIT | Collected: 2026-10-28
# Commit:  863324dfb752
extends "./row_ui.gd"

@export var line_edit_x:LineEdit
@export var line_edit_y:LineEdit
@export var joystick_button:PankuButton

func get_ui_val():
	return Vector2(
		line_edit_x.text.to_float(), 
		line_edit_y.text.to_float())

func update_ui(val:Vector2):
	line_edit_x.text = str(val.x)
	line_edit_y.text = str(val.y)

func is_active() -> bool:
	return line_edit_x.has_focus() or line_edit_y.has_focus()

func _ready():
	line_edit_x.text_submitted.connect(
		func(_s): 
			ui_val_changed.emit(get_ui_val())
	)
	line_edit_y.text_submitted.connect(
		func(_s): 
			ui_val_changed.emit(get_ui_val())
	)
	line_edit_x.focus_exited.connect(
		func(): 
			ui_val_changed.emit(get_ui_val())
	)
	line_edit_y.focus_exited.connect(
		func(): ui_val_changed.emit(get_ui_val())
	)
	var j_button = joystick_button
	j_button.value_changed.connect(
		func(delta:Vector2): 
			update_ui(get_ui_val() + delta)
			ui_val_changed.emit(get_ui_val())
	)
