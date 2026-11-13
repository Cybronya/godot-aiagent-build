# Source:  https://github.com/gdquest-demos/godot-platformer-2d/blob/master/game/src/Player/Skin/Shadow.gd
# Repo:    gdquest-demos/godot-platformer-2d (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  0ea6cb6056dc
extends Sprite


var scale_start := scale


func _ready() -> void:
	set_as_toplevel(true)
