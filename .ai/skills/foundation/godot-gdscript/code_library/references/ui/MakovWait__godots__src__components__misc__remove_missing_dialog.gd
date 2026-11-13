# Source:  https://github.com/MakovWait/godots/blob/main/src/components/misc/remove_missing_dialog.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
class_name RemoveMissingDialog
extends ConfirmationDialog


func _init(callback: Callable) -> void:
	confirmed.connect(callback)
	dialog_text = tr("Remove all missing items from the list?\nThe item folders' contents won't be modified.")
	get_ok_button().text = tr("Remove All")
