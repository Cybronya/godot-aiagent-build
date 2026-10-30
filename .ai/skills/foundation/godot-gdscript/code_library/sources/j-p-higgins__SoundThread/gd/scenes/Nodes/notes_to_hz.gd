extends GraphNode

@export var min_gap: float = 0.5  # editable value in inspector for the minimum gap between min and max
signal open_help

func _ready() -> void:
	#add button to title bar
	var titlebar = self.get_titlebar_hbox()
	var btn = Button.new()
	btn.text = "?"
	btn.tooltip_text = "Open help for " + self.title
	btn.connect("pressed", Callable(self, "_open_help")) #pass key (process name) when button is pressed
	titlebar.add_child(btn)
	
	var i = 0
	while i <= 6:
		$Note.set_item_tooltip_enabled(i, false)
		i += 1
	$Accidental.set_item_tooltip(0, "3/4 Flat")
	$Accidental.set_item_tooltip(1, "Flat")
	$Accidental.set_item_tooltip(2, "1/4 Flat")
	$Accidental.set_item_tooltip(3, "Natural")
	$Accidental.set_item_tooltip(4, "1/4 Sharp")
	$Accidental.set_item_tooltip(5, "Sharp")
	$Accidental.set_item_tooltip(6, "3/4 Sharp")
	
	$Note.select(0, true)
	$Accidental.select(3, true)
	calculate_freq()




func _open_help():
	open_help.emit(self.get_meta("command"), self.title)
	


func _on_item_list_item_selected(index: int) -> void:
	calculate_freq()



func _on_item_list_2_item_selected(index: int) -> void:
	calculate_freq()
	
const NOTE_TO_MIDI = {
	0: 9, 1: 11, 2: 12, 3: 14, 4: 16, 5: 17, 6: 19,
}
const ACCIDENTAL_TO_MODIFIER = {
	0: -1.5, 1: -1, 2: -0.5, 3: 0, 4: 0.5, 5: 1, 6: 1.5,
}

func calculate_freq():
	var note = $Note.get_selected_items()[0]
	var accidental = $Accidental.get_selected_items()[0]
	var freq
	var textout = ""
	
	$FreqOutput.text = ""
	
	note = NOTE_TO_MIDI.get(note, null)
	accidental = ACCIDENTAL_TO_MODIFIER.get(accidental, null)
	
	note = note + accidental
	
	freq = 440.0 * pow(2, (note - 69) / 12.0)
	
	var count = 0
	
	while count < 11:
		textout += "%.2f, " % freq
		freq = freq * 2
		count +=1
	
	$FreqOutput.text = textout
