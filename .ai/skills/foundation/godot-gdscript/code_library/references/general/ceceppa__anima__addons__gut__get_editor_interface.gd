# Source:  https://github.com/ceceppa/anima/blob/main/addons/gut/get_editor_interface.gd
# Repo:    ceceppa/anima (star 769) | License: MIT | Collected: 2026-10-31
# Commit:  f4a454ebd4d5
# This file is here so we can load it only when we are in the editor so that
# other places do not have to have "EditorInterface" in them, which causes a
# parser error when loaded outside of the editor.  The things we have to do in
# order to test things is annoying.
func get_it():
	return EditorInterface