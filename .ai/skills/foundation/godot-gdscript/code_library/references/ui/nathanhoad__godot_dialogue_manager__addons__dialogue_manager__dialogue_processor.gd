# Source:  https://github.com/nathanhoad/godot_dialogue_manager/blob/main/addons/dialogue_manager/dialogue_processor.gd
# Repo:    nathanhoad/godot_dialogue_manager (star 3946) | License: MIT | Collected: 2026-10-26
# Commit:  main
class_name DMDialogueProcessor extends RefCounted


## Override to modify the incoming raw string.
func _preprocess_line(raw_line: String) -> String:
	return raw_line


## Override to modify the outgoing dialogue line.
func _process_line(_line: DMCompiledLine) -> void:
	pass
