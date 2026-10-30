extends GraphNode

var ms = 1000.0
var seconds
var beats
var hz
var MIDI
var samples
var percent
var bpm = 120.0
var samplerate = 44100
var length = 60.0

signal open_help


func _ready() -> void:
	#add button to title bar
	var titlebar = self.get_titlebar_hbox()
	var btn = Button.new()
	btn.text = "?"
	btn.tooltip_text = "Open help for " + self.title
	btn.connect("pressed", Callable(self, "_open_help")) #pass key (process name) when button is pressed
	titlebar.add_child(btn)
	
	$VBoxContainer/HBoxContainer7/BPMEdit.text = str(bpm)
	$VBoxContainer/HBoxContainer5/SampleRateEdit.text = str(samplerate)
	$VBoxContainer/HBoxContainer6/LengthEdit.text = str(length)
	
	calculate()

func _open_help():
	open_help.emit(self.get_meta("command"), self.title)

func calculate():
	seconds = ms / 1000
	beats = (seconds * bpm) / 60
	hz = 1000.0 / ms
	MIDI = 12 * (log(hz / 440) / log(2)) + 69
	samples = seconds * samplerate
	percent = (seconds / length) * 100
	
	$VBoxContainer/HBoxContainer/MsEdit.text = str(ms)
	$VBoxContainer/HBoxContainer2/SEdit.text = str(seconds)
	$VBoxContainer/HBoxContainer7/CrotchetEdit.text = str(beats)
	$VBoxContainer/HBoxContainer3/HzEdit.text = str(hz)
	$VBoxContainer/HBoxContainer4/MIDIEdit.text = str(MIDI)
	$VBoxContainer/HBoxContainer5/SampleNoEdit.text = str(samples)
	$VBoxContainer/HBoxContainer6/PercentEdit.text = str(percent)
	

func _on_ms_edit_text_submitted(new_text: String) -> void:
	if new_text.is_valid_float():
		ms = new_text.to_float()
		calculate()
	else:
		$VBoxContainer/HBoxContainer/MsEdit.text = str(ms)

func _on_ms_edit_focus_exited() -> void:
	_on_ms_edit_text_submitted($VBoxContainer/HBoxContainer/MsEdit.text)

func _on_s_edit_text_submitted(new_text: String) -> void:
	if new_text.is_valid_float():
		ms = new_text.to_float() * 1000
		calculate()
	else:
		$VBoxContainer/HBoxContainer2/SEdit.text = str(seconds)
		

func _on_s_edit_focus_exited() -> void:
	_on_s_edit_text_submitted($VBoxContainer/HBoxContainer2/SEdit.text)
	

func _on_crotchet_edit_text_submitted(new_text: String) -> void:
	if new_text.is_valid_float():
		ms = (new_text.to_float() * 60000.0) / bpm
		calculate()
	else:
		$VBoxContainer/HBoxContainer7/CrotchetEdit.text = str(beats)
		

func _on_crotchet_edit_focus_exited() -> void:
	_on_crotchet_edit_text_submitted($VBoxContainer/HBoxContainer7/CrotchetEdit.text)
	
func _on_bpm_edit_text_submitted(new_text: String) -> void:
	if new_text.is_valid_float():
		bpm = new_text.to_float()
		ms = (beats * 60000.0) / bpm
		calculate()
	else:
		$VBoxContainer/HBoxContainer7/BPMEdit.text = str(bpm)
		
func _on_bpm_edit_focus_exited() -> void:
	_on_bpm_edit_text_submitted($VBoxContainer/HBoxContainer7/BPMEdit.text)
	
func _on_hz_edit_text_submitted(new_text: String) -> void:
	if new_text.is_valid_float():
		ms = (1.0 / new_text.to_float()) * 1000
		calculate()
	else:
		$VBoxContainer/HBoxContainer3/HzEdit.text = str(hz)


func _on_hz_edit_focus_exited() -> void:
	_on_hz_edit_text_submitted($VBoxContainer/HBoxContainer3/HzEdit.text)
	

func _on_midi_edit_text_submitted(new_text: String) -> void:
	if new_text.is_valid_float():
		var freq = 440.0 * pow(2, (new_text.to_float() - 69) / 12.0)
		ms = (1.0 / freq) * 1000
		calculate()
	else:
		$VBoxContainer/HBoxContainer4/MIDIEdit.text = str(MIDI)
		

func _on_midi_edit_focus_exited() -> void:
	_on_midi_edit_text_submitted($VBoxContainer/HBoxContainer4/MIDIEdit.text)
	

func _on_sample_no_edit_text_submitted(new_text: String) -> void:
	if new_text.is_valid_float():
		ms = (new_text.to_float() / samplerate) * 1000
		calculate()
	else:
		$VBoxContainer/HBoxContainer5/SampleNoEdit.text = str(samples)
		

func _on_sample_no_edit_focus_exited() -> void:
	_on_sample_no_edit_text_submitted($VBoxContainer/HBoxContainer5/SampleNoEdit.text)
	
func _on_sample_rate_edit_text_submitted(new_text: String) -> void:
	if new_text.is_valid_float():
		samplerate = new_text.to_float()
		ms = (samples / samplerate) * 1000
		calculate()
	else:
		$VBoxContainer/HBoxContainer5/SampleRateEdit.text = str(samplerate)
		
func _on_sample_rate_edit_focus_exited() -> void:
	_on_sample_rate_edit_text_submitted($VBoxContainer/HBoxContainer5/SampleRateEdit.text)
	
func _on_percent_edit_text_submitted(new_text: String) -> void:
	if new_text.is_valid_float():
		ms = (new_text.to_float() / 100.0) * (length * 1000)
		calculate()
	else:
		$VBoxContainer/HBoxContainer6/PercentEdit.text = str(percent)
		

func _on_percent_edit_focus_exited() -> void:
	_on_percent_edit_text_submitted($VBoxContainer/HBoxContainer6/PercentEdit.text)
	
func _on_length_edit_text_submitted(new_text: String) -> void:
	if new_text.is_valid_float():
		length = new_text.to_float()
		ms = (percent / 100.0) * (length * 1000)
		calculate()
	else:
		$VBoxContainer/HBoxContainer6/LengthEdit.text = str(length)
		

func _on_length_edit_focus_exited() -> void:
	_on_length_edit_text_submitted($VBoxContainer/HBoxContainer6/LengthEdit.text)
