# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/windows/line_dialog/line_dialog.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends Window


signal return_string(status)


func set_value(v) -> void:
	$VBoxContainer/LineEdit.text = v

func _on_OK_pressed() -> void:
	_on_LineEdit_text_entered($VBoxContainer/LineEdit.text)

func _on_LineEdit_text_entered(new_text) -> void:
	emit_signal("return_string", { ok=true, text=new_text })
	queue_free()

func _on_Cancel_pressed():
	emit_signal("return_string", { ok=false })
	queue_free()

func enter_text(window_title : String, label : String, value : String) -> Dictionary:
	title = window_title
	$VBoxContainer/Label.text = label
	$VBoxContainer/LineEdit.grab_focus()
	$VBoxContainer/LineEdit.grab_click_focus()
	set_value(value)
	$VBoxContainer/LineEdit.grab_focus()
	$VBoxContainer/LineEdit.grab_click_focus()
	hide()
	_on_VBoxContainer_minimum_size_changed()
	popup_centered()
	var result = await self.return_string
	queue_free()
	return result

func _on_VBoxContainer_minimum_size_changed():
	size = ($VBoxContainer.get_minimum_size() + Vector2(20, 4))*content_scale_factor

func _on_ready() -> void:
	content_scale_factor = mm_globals.ui_scale_factor()
