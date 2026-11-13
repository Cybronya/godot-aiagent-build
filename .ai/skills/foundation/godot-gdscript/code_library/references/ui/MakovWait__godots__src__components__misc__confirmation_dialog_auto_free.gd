# Source:  https://github.com/MakovWait/godots/blob/main/src/components/misc/confirmation_dialog_auto_free.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
class_name ConfirmationDialogAutoFree
extends ConfirmationDialog


func _ready() -> void:
	visibility_changed.connect(func() -> void: 
		if not visible:
			queue_free()
	)
	confirmed.connect(func() -> void:
		queue_free()
	)
