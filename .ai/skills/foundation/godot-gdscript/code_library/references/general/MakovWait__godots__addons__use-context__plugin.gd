# Source:  https://github.com/MakovWait/godots/blob/main/addons/use-context/plugin.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
@tool
extends EditorPlugin


const AUTOLOAD_NAME = "Context"


func _enter_tree():
	add_autoload_singleton(AUTOLOAD_NAME, "res://addons/use-context/context_node.gd")


func _exit_tree():
	remove_autoload_singleton(AUTOLOAD_NAME)
