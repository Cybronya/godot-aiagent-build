# Source:  https://github.com/MakovWait/godots/blob/main/src/components/editors/local/editor_item/add_extra_arguments_editor_dialog.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
class_name AddExtraArgumentsEditorDialog
extends ConfirmationDialogAutoFree

signal editor_add_extra_arguments(args: PackedStringArray)

@onready var _array_edit := %ArrayEdit as ArrayEdit


func _ready() -> void:
	super._ready()
	min_size = Vector2(300, 0) * Config.EDSCALE
	
	confirmed.connect(func() -> void:
		editor_add_extra_arguments.emit(_array_edit.get_array())
	)


func init(initial_args: PackedStringArray) -> void:
	_array_edit.override_array(initial_args)
