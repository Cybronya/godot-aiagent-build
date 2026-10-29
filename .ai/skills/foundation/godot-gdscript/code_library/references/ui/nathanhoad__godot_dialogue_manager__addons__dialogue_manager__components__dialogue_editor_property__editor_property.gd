# Source:  https://github.com/nathanhoad/godot_dialogue_manager/blob/main/addons/dialogue_manager/components/dialogue_editor_property/editor_property.gd
# Repo:    nathanhoad/godot_dialogue_manager (star 3946) | License: MIT | Collected: 2026-10-26
# Commit:  ebfc3f0cb6e1
@tool

class_name DMDialogueEditorProperty extends EditorProperty


const DialoguePropertyEditorControl: PackedScene = preload("./editor_property_control.tscn")


var control: Control = DialoguePropertyEditorControl.instantiate()
var current_value: DialogueResource


func _init() -> void:
	add_child(control)

	control.resource = current_value

	control.resource_changed.connect(_on_resource_changed)


func _update_property() -> void:
	var next_value: DialogueResource = get_edited_object()[get_edited_property()]

	# The resource might have been deleted elsewhere so check that it's not in a weird state
	if is_instance_valid(next_value) and not next_value.resource_path.ends_with(".dialogue"):
		emit_changed(get_edited_property(), null)
		return

	if next_value == current_value: return

	current_value = next_value
	control.resource = current_value


#region Signals


func _on_resource_changed(next_resource: DialogueResource) -> void:
	emit_changed(get_edited_property(), next_resource)


#endregion
