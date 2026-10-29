# Source:  https://github.com/viniciusgerevini/godot-aseprite-wizard/blob/godot_4/addons/AsepriteWizard/interface/imports_manager/tree_filter_field.gd
# Repo:    viniciusgerevini/godot-aseprite-wizard (star 1396) | License: MIT | Collected: 2026-10-29
# Commit:  18ebea9868ea
@tool
extends LineEdit

signal change_finished(text: String)

@export var debounce_time_in_seconds: float = 0.3

var _time_since_last_change: float = 0.0
var _has_pending_changes: bool = false


func _process(delta: float) -> void:
	if _has_pending_changes:
		_time_since_last_change += delta
		if _time_since_last_change > debounce_time_in_seconds:
			_has_pending_changes = false
			change_finished.emit(self.text)


func _on_text_changed(_new_text: String) -> void:
	_has_pending_changes = true
	_time_since_last_change = 0
