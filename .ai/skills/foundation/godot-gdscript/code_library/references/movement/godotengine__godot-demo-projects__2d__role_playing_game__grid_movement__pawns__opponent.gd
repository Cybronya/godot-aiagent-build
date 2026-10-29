# Source:  https://github.com/godotengine/godot-demo-projects/blob/master/2d/role_playing_game/grid_movement/pawns/opponent.gd
# Repo:    godotengine/godot-demo-projects (star 9711) | License: MIT | Collected: 2026-10-26
# Commit:  b761b4cd5718
extends Walker

func _ready() -> void:
	super._ready()
	set_process(false)
