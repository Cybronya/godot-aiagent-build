# Source:  https://github.com/Maaack/Godot-Game-Template/blob/main/addons/maaacks_game_template/extras/scripts/capture_mouse.gd
# Repo:    Maaack/Godot-Game-Template (star 1709) | License: MIT | Collected: 2026-10-26
# Commit:  5cc611f7dfcd
extends Control
## Control node that captures the mouse for games that require it. 
##
## Used for games that use the mouse to move the camera (ex. FPS or third-person shooters).

var prior_mouse_mode : Input.MouseMode

func _gui_input(event):
	if event is InputEventMouseButton and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
		prior_mouse_mode = Input.mouse_mode
		Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)

func _exit_tree():
	Input.set_mouse_mode(prior_mouse_mode)
