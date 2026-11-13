# Source:  https://github.com/MakovWait/godots/blob/main/src/components/misc/scan_file_dialog.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
class_name ScanFileDialog
extends FileDialog

signal dir_to_scan_selected(dir: String)


func _init() -> void:
	title = tr("Select a Folder to Scan")
	dir_selected.connect(func(dir: String) -> void:
		dir_to_scan_selected.emit(dir)
	)


func _ready() -> void:
	file_mode = FileDialog.FILE_MODE_OPEN_DIR
	access = FileDialog.ACCESS_FILESYSTEM
