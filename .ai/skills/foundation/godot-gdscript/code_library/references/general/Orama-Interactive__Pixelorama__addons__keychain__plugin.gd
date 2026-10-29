# Source:  https://github.com/Orama-Interactive/Pixelorama/blob/master/addons/keychain/plugin.gd
# Repo:    Orama-Interactive/Pixelorama (star 10855) | License: MIT | Collected: 2026-10-27
# Commit:  fae9327992f1
@tool
extends EditorPlugin


func _enter_tree() -> void:
	add_autoload_singleton("Keychain", "res://addons/keychain/Keychain.gd")


func _exit_tree() -> void:
	remove_autoload_singleton("Keychain")
