extends GraphNode
signal open_help
signal node_moved

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	#add button to title bar
	var titlebar = self.get_titlebar_hbox()
	var btn = Button.new()
	btn.text = "?"
	btn.tooltip_text = "Open help for " + self.title
	btn.connect("pressed", Callable(self, "_open_help")) #pass key (process name) when button is pressed
	titlebar.add_child(btn)
	
	self.position_offset_changed.connect(_on_position_offset_changed)
	
func init():
	var interface_settings = ConfigHandler.load_interface_settings()
	$DeleteIntermediateFilesToggle.button_pressed = interface_settings.get("delete_intermediate", true)
	$ReuseFolderToggle.button_pressed = interface_settings.get("reuse_output_folder", true)
	$HBoxContainer/Autoplay.button_pressed = interface_settings.get("autoplay", true)


func _open_help():
	open_help.emit(self.get_meta("command"), self.title)

func _on_autoplay_toggled(toggled_on: bool) -> void:
	ConfigHandler.save_interface_settings("autoplay", toggled_on)
	$AudioPlayer.autoplay = toggled_on


func _on_delete_intermediate_files_toggle_toggled(toggled_on: bool) -> void:
	ConfigHandler.save_interface_settings("delete_intermediate", toggled_on)


func _on_reuse_folder_toggle_toggled(toggled_on: bool) -> void:
	ConfigHandler.save_interface_settings("reuse_output_folder", toggled_on)

func _on_position_offset_changed():
	node_moved.emit(self, Rect2(position, size))


func _on_file_name_field_text_submitted(new_text: String) -> void:
	#check for slashes which can't be in a file name
	if new_text.contains("/"):
		new_text = new_text.replace("/", "")
	if new_text.contains("\\"):
		new_text = new_text.replace("\\", "")
		
	var check_characters = Global.check_for_invalid_chars(new_text)
	if check_characters["contains_invalid_characters"] == true:
		$FileNameField.text = check_characters["string_without_invalid_characters"]


func _on_file_name_field_focus_exited() -> void:
	_on_file_name_field_text_submitted($FileNameField.text)
