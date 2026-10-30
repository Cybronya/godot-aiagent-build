extends GraphNode
signal open_help
signal node_moved

func _ready() -> void:
	#add button to title bar
	var titlebar = self.get_titlebar_hbox()
	var btn = Button.new()
	btn.text = "?"
	btn.tooltip_text = "Open help for " + self.title
	btn.connect("pressed", Callable(self, "_open_help")) #pass key (process name) when button is pressed
	titlebar.add_child(btn)
	
	$AudioPlayer.setnodetitle.connect(_set_node_title)
	
	self.position_offset_changed.connect(_on_position_offset_changed)

func _open_help():
	open_help.emit(self.get_meta("command"), self.title)

func _set_node_title(file: String):
	file = file.get_basename()
	if file.length() > 30:
		file = file.substr(0, 30) + "..."
	title = "Input File - " + file

func _on_position_offset_changed():
	node_moved.emit(self, Rect2(position, size))
