# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/windows/material_editor/expression_line_edit.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
extends LineEdit


var parent_dialog : Object


func _on_Button_pressed():
	var expression_editor : Window = load("res://material_maker/widgets/float_edit/expression_editor.tscn").instantiate()
	add_child(expression_editor)
	var expression = parent_dialog.get_expression_from_output(text)
	expression_editor.edit_parameter("Expression editor", expression, self, "set_value_from_expression_editor")
	accept_event()

func set_value_from_expression_editor(v : String):
	text = v
	emit_signal("text_submitted", v)
