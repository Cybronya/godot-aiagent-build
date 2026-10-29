# Source:  https://github.com/protongraph/protongraph/blob/main/ui/views/editor/graph_editor/components/nodes/boolean.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
class_name BooleanComponent
extends GenericInputComponent


var _checkbox: CheckBox


func initialize(label_name: String, type: int, opts := SlotOptions.new()):
	super(label_name, type, opts)
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	_checkbox = CheckBox.new()
	_checkbox.focus_mode = Control.FOCUS_NONE
	_checkbox.name = "CheckBox"
	_checkbox.button_pressed = opts.get_default_value(false)
	_checkbox.size_flags_vertical = Control.SIZE_SHRINK_BEGIN

	add_ui(_checkbox)
	_checkbox.toggled.connect(_on_value_changed)


func get_value() -> bool:
	return _checkbox.button_pressed


func set_value(value: bool) -> void:
	_checkbox.button_pressed = value


func notify_connection_changed(connected: bool) -> void:
	_checkbox.visible = !connected


func _on_value_changed(val: bool) -> void:
	super(val)
