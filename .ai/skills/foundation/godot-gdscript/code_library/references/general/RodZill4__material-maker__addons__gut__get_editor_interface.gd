# Source:  https://github.com/RodZill4/material-maker/blob/master/addons/gut/get_editor_interface.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
# This file is here so we can load it only when we are in the editor so that
# other places do not have to have "EditorInterface" in them, which causes a
# parser error when loaded outside of the editor.  The things we have to do in
# order to test things is annoying.
func get_it():
	return EditorInterface