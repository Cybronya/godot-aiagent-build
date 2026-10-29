# Source:  https://github.com/bitbrain/pandora/blob/godot-4.x/addons/pandora/ui/components/properties/string/string_property.gd
# Repo:    bitbrain/pandora (star 1129) | License: MIT | Collected: 2026-10-29
# Commit:  fa48e30e6609
@tool
extends PandoraPropertyControl


@onready var line_edit: LineEdit = $LineEdit


func _ready() -> void:
	refresh()
	line_edit.focus_exited.connect(func(): unfocused.emit())
	line_edit.focus_entered.connect(func(): focused.emit())
	line_edit.text_changed.connect(
		func(text:String):
			_property.set_default_value(text)
			property_value_changed.emit(text))


func refresh() -> void:
	if _property != null:
		var value = _property.get_default_value() as String
		if value != line_edit.text:
			line_edit.text = value
