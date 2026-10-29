# Source:  https://github.com/protongraph/protongraph/blob/main/ui/views/editor/graph_editor/components/nodes/dropdown.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
class_name DropdownComponent
extends GenericInputComponent


var _dropdown: OptionButton


func initialize(label_name: String, type: int, opts := SlotOptions.new()) -> void:
	super(label_name, type, opts)

	_dropdown = OptionButton.new()
	add_ui(_dropdown)
	_dropdown.focus_mode = Control.FOCUS_NONE
	_dropdown.name = "OptionButton"
	_dropdown.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	for item in opts.dropdown_items:
		_dropdown.add_item(item.label, item.id)

	# Select the default value if any
	if opts.value != null:
		var idx = _dropdown.get_item_index(opts.value)
		_dropdown.select(idx)

	_dropdown.item_selected.connect(_on_value_changed)


func get_value() -> int:
	return _dropdown.get_selected_id()


func set_value(value: int) -> void:
	_dropdown.selected = _dropdown.get_item_index(value)


func _on_value_changed(item_index: int) -> void:
	super(_dropdown.get_item_id(item_index))


func notify_connection_changed(connected: bool) -> void:
	_dropdown.visible = !connected
