# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/widgets/text_line_edit/text_line_edit.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
extends LineEdit

class_name TextLineEdit

func _init() -> void:
	var menu : PopupMenu = get_menu()

	menu.item_count = 0
	menu.add_item("Edit text", MENU_MAX + 1)
	menu.add_item("Clear", MENU_CLEAR)
 
	menu.add_separator()
	menu.add_item("Undo", MENU_UNDO)
	menu.add_item("Redo", MENU_REDO)
	menu.add_separator()
	menu.add_item("Cut", MENU_CUT)
	menu.add_item("Copy", MENU_COPY)
	menu.add_item("Paste", MENU_PASTE)
	menu.add_separator()
	menu.add_item("Select All", MENU_SELECT_ALL)

	menu.id_pressed.connect(func(id):
		match id:
			MENU_MAX + 1:
				var text_editor : Window = load(
						"res://material_maker/widgets/text_line_edit/text_editor_dialog.tscn").instantiate()
				add_child(text_editor)
				text_editor.edit_text("Text Editor", text, self, "update_text_string")
		)

func update_text_string(v : String):
	text = v
	emit_signal("text_changed", v)
	emit_signal("text_submitted", v)
