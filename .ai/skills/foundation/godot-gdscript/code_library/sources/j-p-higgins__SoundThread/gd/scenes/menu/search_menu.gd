extends PopupPanel

@onready var item_container: VBoxContainer = $VBoxContainer/ScrollContainer/ItemContainer
@onready var scroll_container: ScrollContainer = $VBoxContainer/ScrollContainer
@onready var search_bar = $VBoxContainer/SearchBar
@onready var mode_label = $VBoxContainer/ReplaceLabel
var node_data = {} #stores node data for each node to display in help popup
var replace_node = false
var node_to_replace
var connect_to_node = false
var node_to_connect_to
var uiscale
var favourites
signal make_node(command)
signal swap_node(node_to_replace, command)
signal connect_to_clicked_node(node_to_connect_to, command)


func _ready() -> void:
	#parse json
	var file = FileAccess.open("res://scenes/main/process_help.json", FileAccess.READ)
	if file:
		var result = JSON.parse_string(file.get_as_text())
		if typeof(result) == TYPE_DICTIONARY:
			node_data = result
		else:
			push_error("Invalid JSON")
				
	#honestly not sure what of these is actually doing things
	item_container.custom_minimum_size.x = scroll_container.size.x
	scroll_container.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll_container.set("theme_override_constants/maximum_height", 400)



func _on_about_to_popup() -> void:
	var interface_settings = ConfigHandler.load_interface_settings()
	favourites = interface_settings.favourites
	display_items("") #populate menu when needed
	search_bar.clear()
	search_bar.grab_focus()
	

func display_items(filter: String):
	# Remove all existing items from the VBoxContainer
	for child in item_container.get_children():
		child.queue_free()
		
	var filters = filter.to_lower().split(" ", false)
	
	for key in node_data.keys():
		var item = node_data[key]
		var title = item.get("title", "")
		
		#check if searching for favourites
		if filters.has("*"):
			if favourites.has(key) == false:
				continue
		
		#filter out output node
		if title == "Output File":
			continue
		
		var category = item.get("category", "")
		var subcategory = item.get("subcategory", "")
		var short_desc = item.get("short_description", "")
		var command = key.replace("_", " ")
		
		
		# Combine all searchable text into one lowercase string
		var searchable_text = "%s %s %s %s %s" % [title, short_desc, category, subcategory, key]
		searchable_text = searchable_text.to_lower()
		
		# If filter is not empty, skip non-matches populate all other buttons
		if filter != "":
			var match_all_words = true
			for word in filters:
				if word == "*":
					continue
					
				if word != "" and not searchable_text.findn(word) != -1:
					match_all_words = false
					break
			if not match_all_words:
				continue
		
		var btn = Button.new()
		btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL #make buttons wide
		btn.alignment = 0 #left align text
		btn.clip_text = true #clip off labels that are too long
		btn.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS #and replace with ...
		var button_text = ""
		if favourites.has(key):
			button_text += "★ "
		if category.to_lower() == "pvoc": #format node names correctly, only show the category for PVOC
			button_text += "%s %s: %s - %s" % [category.to_upper(), subcategory.to_pascal_case(), title, short_desc]
		elif title.to_lower() == "input file":
			button_text += "%s - %s" % [title, short_desc]
		else:
			button_text += "%s: %s - %s" % [subcategory.to_pascal_case(), title, short_desc]
		btn.text = button_text
		btn.connect("pressed", Callable(self, "_on_item_selected").bind(key)) #pass key (process name) when button is pressed
		
		#apply custom focus theme for keyboard naviagation
		var theme := Theme.new()
		var style_focus := StyleBoxFlat.new()
		style_focus.bg_color = Color.hex(0xffffff4a)
		theme.set_stylebox("focus", "Button", style_focus)
		btn.theme = theme
		
		item_container.add_child(btn)
	
	#resize menu within certain bounds #50
	await get_tree().process_frame
	#if DisplayServer.screen_get_dpi(0) >= 144:
		#self.size.y = min((item_container.size.y + search_bar.size.y + 12) * 2, 820) #i think this will scale for retina screens but might be wrong
	#else:
	if mode_label.visible:
		self.size.y = min((item_container.size.y + search_bar.size.y + 16 + mode_label.size.y) * uiscale, 410 * uiscale)
	else:
		self.size.y = min((item_container.size.y + search_bar.size.y + 12) * uiscale, 410 * uiscale)
	
	#highlight first button
	_on_search_bar_editing_toggled(true)
	
func _on_search_bar_text_changed(new_text: String) -> void:
	display_items(new_text)
	
func _on_item_selected(key: String):
	self.hide()
	if replace_node == true:
		swap_node.emit(node_to_replace, key)
	elif connect_to_node == true:
		connect_to_clicked_node.emit(node_to_connect_to, key)
	else:
		make_node.emit(key) # send out signal to main patch

func _on_search_bar_text_submitted(new_text: String) -> void:
	var button = item_container.get_child(0)
	if button and button is Button:
		button.emit_signal("pressed")


func _on_search_bar_editing_toggled(toggled_on: bool) -> void:
	#highlight first button when editing is toggled
	var button = item_container.get_child(0)
	if toggled_on:
		if button and button is Button:
			var base_stylebox = button.get_theme_stylebox("normal", "Button")
			var new_stylebox = base_stylebox.duplicate()
			new_stylebox.bg_color = Color.hex(0xffffff4a)
			button.add_theme_stylebox_override("normal", new_stylebox)
			#skip this button on tab navigation
			button.focus_mode = Control.FOCUS_CLICK
	else:
		if button and button is Button:
			button.remove_theme_stylebox_override("normal")
