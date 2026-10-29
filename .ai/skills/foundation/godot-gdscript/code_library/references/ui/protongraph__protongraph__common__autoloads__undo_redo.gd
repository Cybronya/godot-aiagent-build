# Source:  https://github.com/protongraph/protongraph/blob/main/common/autoloads/undo_redo.gd
# Repo:    protongraph/protongraph (star 1749) | License: MIT | Collected: 2026-10-29
# Commit:  1e2411a29464
extends Node


var undo_redo: UndoRedo


func _ready() -> void:
	undo_redo = get_undo_redo()


func get_undo_redo() -> UndoRedo:
	if not undo_redo:
		undo_redo = UndoRedo.new()
	return undo_redo


func _input(_event: InputEvent) -> void:
	# The order matters because of how the shortcuts are defined
	if Input.is_action_just_released("ui_redo"):
		undo_redo.redo()
	elif Input.is_action_just_released("ui_undo"):
		undo_redo.undo()
