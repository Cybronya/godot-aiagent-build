# Source:  https://github.com/MakovWait/godots/blob/main/src/auto_native_file_dialog.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
extends Node


func _enter_tree() -> void:
	get_tree().node_added.connect(_on_node_added)


func _exit_tree() -> void:
	get_tree().node_added.disconnect(_on_node_added)


func _on_node_added(node: Node) -> void:
	if node is FileDialog:
		(node as FileDialog).use_native_dialog = Config.USE_NATIVE_FILE_DIALOG.ret() as bool
