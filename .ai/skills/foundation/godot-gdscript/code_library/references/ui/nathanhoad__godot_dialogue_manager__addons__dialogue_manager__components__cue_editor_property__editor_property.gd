# Source:  https://github.com/nathanhoad/godot_dialogue_manager/blob/main/addons/dialogue_manager/components/cue_editor_property/editor_property.gd
# Repo:    nathanhoad/godot_dialogue_manager (star 3946) | License: MIT | Collected: 2026-10-26
# Commit:  main
@tool
class_name DMCueEditorProperty extends EditorProperty


var DMCuePropertyEditorControl: PackedScene = preload("./editor_property_control.tscn")
var control: Control = DMCuePropertyEditorControl.instantiate()
var current_value: String
var is_updating: bool = false


func _init() -> void:
	add_child(control)

	control.cue = current_value

	control.cue_changed.connect(_on_cue_changed)


func _update_property() -> void:
	control.actionable = get_edited_object()

	var next_value: String = get_edited_object()[get_edited_property()]

	if next_value.is_empty():
		control.cue = ""
		return

	if next_value == current_value: return

	is_updating = true
	current_value = next_value
	control.cue = current_value
	is_updating = false


#region Signals


func _on_cue_changed(next_cue: String) -> void:
	emit_changed(get_edited_property(), next_cue)


#endregion
