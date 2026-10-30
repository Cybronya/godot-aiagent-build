extends Control

signal add_inlet
signal remove_inlet
var undo_redo: UndoRedo
var minimum_inlet_count
var maximum_inlet_count
var current_inlet_count

func _ready() -> void:
	minimum_inlet_count = get_meta("min")
	maximum_inlet_count = get_meta("max")
	current_inlet_count = get_meta("default")
	check_buttons()


func _on_add_inlet_button_button_down() -> void:
	undo_redo.create_action("Add Inlet")
	undo_redo.add_do_method(add_new)
	undo_redo.add_undo_method(remove)
	undo_redo.commit_action()
	
func add_new() -> void:
	add_inlet.emit()
	current_inlet_count += 1
	set_meta("inlet_count", current_inlet_count)
	check_buttons()


func _on_remove_inlet_button_button_down() -> void:
	undo_redo.create_action("Remove Inlet")
	undo_redo.add_do_method(remove)
	undo_redo.add_undo_method(add_new)
	undo_redo.commit_action()
	
func remove() -> void:
	remove_inlet.emit()
	current_inlet_count -= 1
	set_meta("inlet_count", current_inlet_count)
	check_buttons()

func check_buttons():
	if current_inlet_count == maximum_inlet_count:
		$VBoxContainer/HBoxContainer/AddInletButton.disabled = true
	else:
		$VBoxContainer/HBoxContainer/AddInletButton.disabled = false
		
	if current_inlet_count == minimum_inlet_count:
		$VBoxContainer/HBoxContainer/RemoveInletButton.disabled = true
	else:
		$VBoxContainer/HBoxContainer/RemoveInletButton.disabled = false
		
func restore_inlets():
	print("current meta for inlet count is " + str(get_meta("inlet_count")))
	var restore_inlet_count = get_meta("inlet_count")
	while restore_inlet_count > current_inlet_count:
		_on_add_inlet_button_button_down()
	
	while restore_inlet_count < current_inlet_count:
		_on_remove_inlet_button_button_down()
		
	print("current inlet count is " + str(current_inlet_count))
