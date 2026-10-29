# Source:  https://github.com/hi-godot/godot-ai/blob/main/plugin/addons/godot_ai/handlers/command_handler.gd
# Repo:    hi-godot/godot-ai (star 3268) | License: MIT | Collected: 2026-10-29
# Commit:  a799acfa49cd
@tool
extends RefCounted

## Built-in handlers execute synchronously, or register every detached
## coroutine with ScriptWork. Client/vision OS workers belong to the root's
## worker owners and are joined separately before any scripts are replaced.
## New async entry points MUST retain their ledger entry until they return,
## including early returns; a request timeout/disconnect must not clear it.
const ScriptWork := preload("res://addons/godot_ai/utils/script_work.gd")


func quiesce_for_script_swap() -> Dictionary:
	return ScriptWork.quiescence()
