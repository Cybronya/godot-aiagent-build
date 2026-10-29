# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Editor/Inspector/inspector_plugin.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  701b67bbe601
@tool
extends EditorInspectorPlugin


func _can_handle(_object: Object) -> bool:
	return true


func _parse_property(_object: Object, type: Variant.Type, name: String, hint_type: PropertyHint, hint_string: String, _usage_flags: int, _wide: bool) -> bool:
	if type == TYPE_OBJECT and hint_type == PROPERTY_HINT_RESOURCE_TYPE:
		if hint_string == "DialogicTimeline":
			var editor: EditorProperty = load("res://addons/dialogic/Editor/Inspector/timeline_inspector_field.gd").new()
			add_property_editor(name, editor)
			return true
	return false
