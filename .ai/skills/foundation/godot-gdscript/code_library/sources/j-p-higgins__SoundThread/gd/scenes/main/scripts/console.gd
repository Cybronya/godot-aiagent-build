extends Window


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	pass # Replace with function body.


func _on_console_output_gui_input(event: InputEvent) -> void:
	#check if right click on console and if so open context menu
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_RIGHT and event.pressed:
		var local_pos = DisplayServer.mouse_get_position()
		$ConsoleRightClick.position = local_pos
		$ConsoleRightClick.popup()



func _on_console_right_click_index_pressed(index: int) -> void:
	match index:
		0:
			#select all text in the console
			$ConsoleOutput.select_all()
		1:
			#copy selected text in the console to the clipboard
			var selection = $ConsoleOutput.get_selected_text()
			if selection != "":
				DisplayServer.clipboard_set(selection)
