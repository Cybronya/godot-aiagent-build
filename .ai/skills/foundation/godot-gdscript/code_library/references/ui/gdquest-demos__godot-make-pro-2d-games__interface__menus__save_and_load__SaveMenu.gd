# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/interface/menus/save_and_load/SaveMenu.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends Menu

onready var save_button = $Panel/Column/SaveButton
onready var load_button = $Panel/Column/LoadButton

func open(args={}):
	.open()
	save_button.grab_focus()
