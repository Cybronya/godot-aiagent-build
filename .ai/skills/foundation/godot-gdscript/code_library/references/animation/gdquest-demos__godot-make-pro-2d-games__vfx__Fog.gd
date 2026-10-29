# Source:  https://github.com/gdquest-demos/godot-make-pro-2d-games/blob/master/vfx/Fog.gd
# Repo:    gdquest-demos/godot-make-pro-2d-games (star 1276) | License: MIT | Collected: 2026-10-29
# Commit:  7290681309ff
extends ColorRect

func _on_LevelLoader_loaded(level):
	visible = level.fog
