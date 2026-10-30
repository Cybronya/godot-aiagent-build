extends Window

var node_data = {} #stores node data for each node to display in help popup
signal make_node(command)
signal open_help(command)

@onready var fav_button_logic = preload("res://scenes/menu/fav_button.gd")


func _ready() -> void:
	
	$"Control/select_effect/Time Domain".show()
	$"Control/select_effect/Time Domain/Distort".show()
	$"Control/select_effect/Frequency Domain/Convert".show()
	#parse json
	var file = FileAccess.open("res://scenes/main/process_help.json", FileAccess.READ)
	if file:
		var result = JSON.parse_string(file.get_as_text())
		if typeof(result) == TYPE_DICTIONARY:
			node_data = result
		else:
			push_error("Invalid JSON")
				
	fill_menu()
	load_search()
	
	#chec user prefs fr favourites and load them
	var interface_settings = ConfigHandler.load_interface_settings()
	var favourites = interface_settings.favourites
	
	_load_favourites(favourites)
	
func fill_menu():
	var interface_settings = ConfigHandler.load_interface_settings()
	var favourites = interface_settings.favourites
	
	for key in node_data.keys():
		var item = node_data[key]
		var title = item.get("title", "")
		
		#filter out output nodes
		if title == "Output File":
			continue
		
		var category = item.get("category", "")
		var subcategory = item.get("subcategory", "")
		var short_desc = item.get("short_description", "")
		
		var container
		if category == "time":
			if subcategory == "distort":
				container = $"Control/select_effect/Time Domain/Distort/MarginContainer/ScrollContainer/DistortContainer"
			elif subcategory == "extend":
				container = $"Control/select_effect/Time Domain/Extend/MarginContainer/ScrollContainer/ExtendContainer"
			elif subcategory == "filter":
				container = $"Control/select_effect/Time Domain/Filter/MarginContainer/ScrollContainer/FilterContainer"
			elif subcategory == "granulate":
				container = $"Control/select_effect/Time Domain/Granulate/MarginContainer/ScrollContainer/GranulateContainer"
			elif subcategory == "misc":
				container = $"Control/select_effect/Time Domain/Misc/MarginContainer/ScrollContainer/MiscContainer"
			elif subcategory == "reverb":
				container = $"Control/select_effect/Time Domain/Reverb and Delay/MarginContainer/ScrollContainer/ReverbContainer"
			elif subcategory == "synthesis":
				container = $"Control/select_effect/Time Domain/Synthesis/MarginContainer/ScrollContainer/SynthesisContainer"
			else:
				continue
		elif category == "pvoc":
			if subcategory == "convert":
				container = $"Control/select_effect/Frequency Domain/Convert/MarginContainer/ScrollContainer/PVOCConvertContainer"
			elif subcategory == "amplitude" or subcategory == "pitch":
				container = $"Control/select_effect/Frequency Domain/Amplitude and Pitch/MarginContainer/ScrollContainer/PVOCAmplitudePitchContainer"
			elif subcategory == "combine":
				container = $"Control/select_effect/Frequency Domain/Combine/MarginContainer/ScrollContainer/PVOCCombineContainer"
			elif subcategory == "formants":
				container = $"Control/select_effect/Frequency Domain/Formants/MarginContainer/ScrollContainer/PVOCFormantsContainer"
			elif subcategory == "time":
				container = $"Control/select_effect/Frequency Domain/Time/MarginContainer/ScrollContainer/PVOCTimeContainer"
			elif subcategory == "spectrum":
				container = $"Control/select_effect/Frequency Domain/Spectrum/MarginContainer/ScrollContainer/PVOCSpectrumContainer"
			else:
				continue
		elif category == "utility":
			container = $Control/select_effect/Utilities/SoundThread/MarginContainer/ScrollContainer/UtilityContainer
		else:
			continue
		
		
		var hbox = HBoxContainer.new()
		var label = RichTextLabel.new()
		var favbtn = Button.new()
		var helpbtn = Button.new()
		var makebtn = Button.new()
		var margin = MarginContainer.new()
		
		hbox.size.x = container.size.x
		label.bbcode_enabled = true
		label.text = "[b]%s[/b]\n%s" % [title, short_desc]
		label.set_h_size_flags(Control.SIZE_EXPAND_FILL)
		label.set_v_size_flags(Control.SIZE_EXPAND_FILL)
		label.fit_content = true
		
		favbtn.name = "fav_" + key
		favbtn.add_theme_font_size_override("font_size", 20)
		favbtn.tooltip_text = "Favourite " + title
		favbtn.custom_minimum_size = Vector2(40, 40)
		favbtn.set_h_size_flags(Control.SIZE_SHRINK_CENTER)
		favbtn.toggle_mode = true
		if favourites.has(key):
			favbtn.text = "★"
			favbtn.set_pressed_no_signal(true)
		else:
			favbtn.text = "☆"
		favbtn.set_script(fav_button_logic)
		favbtn.connect("toggled", Callable(self, "_favourite_process").bind(key, favourites)) #pass key (process name) when button is pressed
		
		helpbtn.text = "?"
		helpbtn.tooltip_text = "Open help for " + title
		helpbtn.custom_minimum_size = Vector2(40, 40)
		helpbtn.set_h_size_flags(Control.SIZE_SHRINK_CENTER)
		helpbtn.connect("pressed", Callable(self, "_open_help").bind(key, title)) #pass key (process name) when button is pressed
		
		makebtn.text = "+"
		makebtn.tooltip_text = "Add " + title + " to thread"
		makebtn.custom_minimum_size = Vector2(40, 40)
		makebtn.set_h_size_flags(Control.SIZE_SHRINK_CENTER)
		makebtn.connect("pressed", Callable(self, "_make_node").bind(key)) #pass key (process name) when button is pressed
		
		margin.add_theme_constant_override("margin_bottom", 3)
		
		container.add_child(hbox)
		hbox.add_child(label)
		hbox.add_child(favbtn)
		hbox.add_child(helpbtn)
		hbox.add_child(makebtn)
		container.add_child(margin)



func _on_about_to_popup() -> void:
	#fill_search("")
	$"Control/select_effect/Search/Search for a process in SoundThread/MarginContainer/VBoxContainer/SearchBar".clear()
	if $Control/select_effect.current_tab == 3:
		$"Control/select_effect/Search/Search for a process in SoundThread/MarginContainer/VBoxContainer/SearchBar".grab_focus()
	



func fill_search(filter: String):
	var interface_settings = ConfigHandler.load_interface_settings()
	var favourites = interface_settings.favourites
	# Remove all existing items from the VBoxContainer
	var container = $"Control/select_effect/Search/Search for a process in SoundThread/MarginContainer/VBoxContainer/ScrollContainer/ItemContainer"
	#for child in container.get_children():
		#child.queue_free()
		
	var filters = filter.to_lower().split(" ", false)
	
	
	for key in node_data.keys():
		var item = node_data[key]
		var search_element = container.find_child("search_" + key, true, false)
		var search_margin = container.find_child("search_margin_" + key, true, false)
		var title = item.get("title", "")
		
		if search_element == null:
			continue
		
		if filters.has("*"):
			if favourites.has(key) == false:
				search_element.hide()
				search_margin.hide()
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
					search_element.hide()
					search_margin.hide()
					break
			if not match_all_words:
				continue
				
		search_element.show()
		search_margin.show()
		
		

	

func load_search():
	var interface_settings = ConfigHandler.load_interface_settings()
	var favourites = interface_settings.favourites
	# Remove all existing items from the VBoxContainer
	var container = $"Control/select_effect/Search/Search for a process in SoundThread/MarginContainer/VBoxContainer/ScrollContainer/ItemContainer"
	for child in container.get_children():
		child.queue_free()
		
	
	
	for key in node_data.keys():
		var item = node_data[key]
		var title = item.get("title", "")
		
		
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
		
		
		var hbox = HBoxContainer.new()
		var label = RichTextLabel.new()
		var favbtn = Button.new()
		var helpbtn = Button.new()
		var makebtn = Button.new()
		var margin = MarginContainer.new()
		
		hbox.size.x = container.size.x
		hbox.name = "search_" + key
		margin.name = "search_margin_" + key
		label.bbcode_enabled = true
		label.text = "[b]%s[/b]\n%s" % [title, short_desc]
		label.set_h_size_flags(Control.SIZE_EXPAND_FILL)
		label.set_v_size_flags(Control.SIZE_EXPAND_FILL)
		label.fit_content = true
		
		favbtn.name = "search_fav_" + key
		favbtn.add_theme_font_size_override("font_size", 20)
		favbtn.tooltip_text = "Favourite " + title
		favbtn.custom_minimum_size = Vector2(40, 40)
		favbtn.set_h_size_flags(Control.SIZE_SHRINK_CENTER)
		favbtn.toggle_mode = true
		if favourites.has(key):
			favbtn.text = "★"
			favbtn.set_pressed_no_signal(true)
		else:
			favbtn.text = "☆"
		favbtn.set_script(fav_button_logic)
		favbtn.connect("toggled", Callable(self, "_favourite_process").bind(key, favourites)) #pass key (process name) when button is pressed
		
		
		
		helpbtn.text = "?"
		helpbtn.tooltip_text = "Open help for " + title
		helpbtn.custom_minimum_size = Vector2(40, 40)
		helpbtn.set_h_size_flags(Control.SIZE_SHRINK_CENTER)
		helpbtn.connect("pressed", Callable(self, "_open_help").bind(key, title)) #pass key (process name) when button is pressed
		
		makebtn.text = "+"
		makebtn.tooltip_text = "Add " + title + " to thread"
		makebtn.custom_minimum_size = Vector2(40, 40)
		makebtn.set_h_size_flags(Control.SIZE_SHRINK_CENTER)
		makebtn.connect("pressed", Callable(self, "_make_node").bind(key)) #pass key (process name) when button is pressed
		
		margin.add_theme_constant_override("margin_bottom", 3)
		
		container.add_child(hbox)
		hbox.add_child(label)
		hbox.add_child(favbtn)
		hbox.add_child(helpbtn)
		hbox.add_child(makebtn)
		container.add_child(margin)


	
func _on_search_bar_text_changed(new_text: String) -> void:
	fill_search(new_text)
	pass
	
func _make_node(key: String):
	make_node.emit(key) # send out signal to main patch
	self.hide()

func _open_help(key: String, title: String):
	open_help.emit(key, title) # send out signal to main patch
	self.hide()


func _on_select_effect_tab_changed(tab: int) -> void:
	if tab == 4:
		$"Control/select_effect/Search/Search for a process in SoundThread/MarginContainer/VBoxContainer/SearchBar".grab_focus()

func _favourite_process(toggled_on: bool, key: String, favourites: Array):
	if toggled_on:
		favourites.append(key)
	else:
		favourites.erase(key)
	
	ConfigHandler.save_interface_settings("favourites", favourites)
	
	#find all favourite buttons for this effect and set to the correct state if in serach of favourites window
	if $Control/select_effect.current_tab == 3 or $Control/select_effect.current_tab == 4:
		var button = $Control/select_effect.find_child("fav_" + key, true, false)
		if button != null:
			button.set_pressed_no_signal(toggled_on)
			if toggled_on:
				button.text = "★"
			else:
				button.text = "☆"
	
	if $Control/select_effect.current_tab != 4:
		var button = $Control/select_effect.find_child("search_fav_" + key, true, false)
		if button != null:
			button.set_pressed_no_signal(toggled_on)
			if toggled_on:
				button.text = "★"
			else:
				button.text = "☆"
	_load_favourites(favourites)
		
func refresh_menu():
	pass


func _load_favourites(favourites: Array):
	var container = $"Control/select_effect/Favourites/Browse Favourites/MarginContainer/VBoxContainer/ScrollContainer/ItemContainer"
	for child in container.get_children():
		child.queue_free()
		
	if favourites.size() > 0:
		for key in node_data.keys():
			var item = node_data[key]
			var title = item.get("title", "")
			
			if favourites.has(key) == false:
				continue
				
			var short_desc = item.get("short_description", "")
			var command = key.replace("_", " ")
			
			var hbox = HBoxContainer.new()
			var label = RichTextLabel.new()
			var favbtn = Button.new()
			var helpbtn = Button.new()
			var makebtn = Button.new()
			var margin = MarginContainer.new()
			
			hbox.size.x = container.size.x
			label.bbcode_enabled = true
			label.text = "[b]%s[/b]\n%s" % [title, short_desc]
			label.set_h_size_flags(Control.SIZE_EXPAND_FILL)
			label.set_v_size_flags(Control.SIZE_EXPAND_FILL)
			label.fit_content = true
			
			favbtn.add_theme_font_size_override("font_size", 20)
			favbtn.tooltip_text = "Favourite " + title
			favbtn.custom_minimum_size = Vector2(40, 40)
			favbtn.set_h_size_flags(Control.SIZE_SHRINK_CENTER)
			favbtn.toggle_mode = true
			if favourites.has(key):
				favbtn.text = "★"
				favbtn.set_pressed_no_signal(true)
			else:
				favbtn.text = "☆"
			favbtn.set_script(fav_button_logic)
			favbtn.connect("toggled", Callable(self, "_favourite_process").bind(key, favourites)) #pass key (process name) when button is pressed
			
			helpbtn.text = "?"
			helpbtn.tooltip_text = "Open help for " + title
			helpbtn.custom_minimum_size = Vector2(40, 40)
			helpbtn.set_h_size_flags(Control.SIZE_SHRINK_CENTER)
			helpbtn.connect("pressed", Callable(self, "_open_help").bind(key, title)) #pass key (process name) when button is pressed
			
			makebtn.text = "+"
			makebtn.tooltip_text = "Add " + title + " to thread"
			makebtn.custom_minimum_size = Vector2(40, 40)
			makebtn.set_h_size_flags(Control.SIZE_SHRINK_CENTER)
			makebtn.connect("pressed", Callable(self, "_make_node").bind(key)) #pass key (process name) when button is pressed
			
			margin.add_theme_constant_override("margin_bottom", 3)
			
			container.add_child(hbox)
			hbox.add_child(label)
			hbox.add_child(favbtn)
			hbox.add_child(helpbtn)
			hbox.add_child(makebtn)
			container.add_child(margin)
	else:
		var label = RichTextLabel.new()
		label.text = "Press the star next to a process in the explore menu to add a favourite."
		label.fit_content = true
		container.add_child(label)
