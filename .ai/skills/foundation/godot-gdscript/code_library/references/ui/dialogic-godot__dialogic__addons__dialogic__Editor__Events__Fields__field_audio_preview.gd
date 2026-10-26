# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Editor/Events/Fields/field_audio_preview.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  main
@tool
extends DialogicVisualEditorField


var file_path: String


func _ready() -> void:
	self.pressed.connect(_on_pressed)
	%AudioStreamPlayer.finished.connect(_on_finished)


#region OVERWRITES
################################################################################


## To be overwritten
func _set_value(value:Variant) -> void:
	file_path = value
	self.disabled = file_path.is_empty()
	_stop()

#endregion


#region SIGNAL METHODS
################################################################################

func _on_pressed() -> void:
	if %AudioStreamPlayer.playing:
		_stop()
	elif not file_path.is_empty():
		_play()


func _on_finished() -> void:
	_stop()

#endregion


func _stop() -> void:
	%AudioStreamPlayer.stop()
	%AudioStreamPlayer.stream = null
	self.icon = get_theme_icon("Play", "EditorIcons")


func _play() -> void:
	if ResourceLoader.exists(file_path):
		%AudioStreamPlayer.stream = load(file_path)
		%AudioStreamPlayer.play()
		self.icon = get_theme_icon("Stop", "EditorIcons")
