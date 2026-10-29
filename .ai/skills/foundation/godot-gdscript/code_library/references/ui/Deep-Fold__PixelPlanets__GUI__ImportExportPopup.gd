# Source:  https://github.com/Deep-Fold/PixelPlanets/blob/main/GUI/ImportExportPopup.gd
# Repo:    Deep-Fold/PixelPlanets (star 1403) | License: MIT | Collected: 2026-10-28
# Commit:  8ec6ee305527
extends ColorRect

signal set_colors

@onready var textedit = $PopupFront/HBoxContainer/VBoxContainer/TextEdit
@onready var apply_button = $PopupFront/HBoxContainer/VBoxContainer2/ApplyColors

var current_colors = []

func set_current_colors(colors):
	current_colors = colors
	textedit.text = ""
	var index = 0
	for c in colors:
		textedit.text += "#" + c.to_html(false)
		if index < colors.size() - 1:
			textedit.text += "\n"
		index += 1

func show_popup():
	visible = true

func _on_CloseButton_pressed():
	visible = false

func _on_CopyToClipboard_pressed():
	DisplayServer.clipboard_set(textedit.text)

func _on_PasteFromClipboard_pressed():
	textedit.text = DisplayServer.clipboard_get()

func _convert_to_colors():
	var text = textedit.text.replace(",", "").split("\n")
	var colors = []
	for t in text:
		t = t.replace(",", "")
		colors.append(Color(t))
	
	for i in range(current_colors.size() - colors.size()):
		colors.append(Color())
	return colors

func _on_ApplyColors_pressed():
	var colors = _convert_to_colors()
	emit_signal("set_colors", colors)
	visible = false
