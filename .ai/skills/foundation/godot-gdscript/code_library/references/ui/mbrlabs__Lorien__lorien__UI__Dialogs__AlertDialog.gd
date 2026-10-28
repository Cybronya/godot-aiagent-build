# Source:  https://github.com/mbrlabs/Lorien/blob/main/lorien/UI/Dialogs/AlertDialog.gd
# Repo:    mbrlabs/Lorien (star 6865) | License: MIT | Collected: 2026-10-27
# Commit:  main
extends AcceptDialog

# ------------------------------------------------------------------------------------------------
func _ready() -> void:
	close_requested.connect(hide)
