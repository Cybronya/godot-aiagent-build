# Source:  https://github.com/Orama-Interactive/Pixelorama/blob/master/addons/dockable_container/inspector_plugin/editor_inspector_plugin.gd
# Repo:    Orama-Interactive/Pixelorama (star 10855) | License: MIT | Collected: 2026-10-27
# Commit:  master
extends EditorInspectorPlugin

const LayoutEditorProperty := preload("layout_editor_property.gd")


func _can_handle(object: Object) -> bool:
	return object is DockableContainer


func _parse_property(
	_object: Object,
	_type: Variant.Type,
	name: String,
	_hint: PropertyHint,
	_hint_text: String,
	_usage: int,
	_wide: bool
) -> bool:
	if name == "layout":
		var editor_property := LayoutEditorProperty.new()
		add_property_editor("layout", editor_property)
	return false
