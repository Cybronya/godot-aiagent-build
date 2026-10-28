# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/windows/desc_dialog/desc_dialog.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends Window


signal close(apply)


func edit_descriptions(type : String, short : String, long : String) -> Array:
	title = type+" Description"
	$VBoxContainer/HBoxContainer/ShortDesc.text = short
	$VBoxContainer/LongDesc.text = long
	_on_WindowDialog_minimum_size_changed()
	hide()
	popup_centered()
	if await self.close:
		short = $VBoxContainer/HBoxContainer/ShortDesc.text
		long = $VBoxContainer/LongDesc.text
	queue_free()
	return [ short, long ]

func _on_OK_pressed():
	emit_signal("close", true)

func _on_Cancel_pressed():
	emit_signal("close", false)

func _on_WindowDialog_popup_hide():
	emit_signal("close", false)

func _on_WindowDialog_minimum_size_changed():
	size = $VBoxContainer.size+Vector2(4, 4)
