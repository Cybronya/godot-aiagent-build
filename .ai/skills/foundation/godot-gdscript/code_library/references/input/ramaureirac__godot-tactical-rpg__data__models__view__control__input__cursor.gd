# Source:  https://github.com/ramaureirac/godot-tactical-rpg/blob/development/data/models/view/control/input/cursor.gd
# Repo:    ramaureirac/godot-tactical-rpg (star 978) | License: MIT | Collected: 2026-10-29
# Commit:  cfe785e5b6f8
class_name CursorService
extends RefCounted
## Handles cursor-related functions for the Tactics system


## Sets the cursor shape to 'move' if it's not already set
static func set_cursor_shape_to_move() -> void:
	if Input.get_current_cursor_shape() != Input.CURSOR_MOVE:
		Input.set_default_cursor_shape(Input.CURSOR_MOVE)


## Sets the cursor shape to 'arrow' if it's not already set
static func set_cursor_shape_to_arrow() -> void:
	if Input.get_current_cursor_shape() != Input.CURSOR_ARROW:
		Input.set_default_cursor_shape(Input.CURSOR_ARROW)
