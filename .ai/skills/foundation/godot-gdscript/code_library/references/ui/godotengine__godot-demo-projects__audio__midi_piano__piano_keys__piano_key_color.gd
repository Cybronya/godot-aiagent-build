# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/audio/midi_piano/piano_keys/piano_key_color.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  master
extends ColorRect

@onready var parent: PianoKey = get_parent()

# Yes, this script exists just for this one method.
func _gui_input(input_event: InputEvent) -> void:
	if input_event is InputEventMouseButton and input_event.pressed:
		parent.activate()
