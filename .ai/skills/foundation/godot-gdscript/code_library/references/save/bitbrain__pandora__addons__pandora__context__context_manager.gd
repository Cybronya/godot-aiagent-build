# Source:  https://github.com/bitbrain/pandora/blob/godot-4.x/addons/pandora/context/context_manager.gd
# Repo:    bitbrain/pandora (star 1129) | License: MIT | Collected: 2026-10-29
# Commit:  fa48e30e6609
## Stores the pandora context. The context influences
## where user data will be stored. Change the context id
## to ensure custom save games for example.
@tool
class_name PandoraContextManager extends RefCounted

# Notifies if the context has changed.
# This can happen if someone changes save games.
signal context_changed

var _context_id: String = ""


func set_context_id(new_context_id: String) -> void:
	_context_id = new_context_id


func get_context_id() -> String:
	return _context_id
