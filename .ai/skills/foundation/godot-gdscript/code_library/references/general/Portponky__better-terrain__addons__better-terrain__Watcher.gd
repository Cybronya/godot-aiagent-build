# Source:  https://github.com/Portponky/better-terrain/blob/main/addons/better-terrain/Watcher.gd
# Repo:    Portponky/better-terrain (star 752) | License: Unlicense | Collected: 2026-10-31
# Commit:  e93040e1cdd9
@tool
extends Node

signal trigger
var complete := false
var tileset : TileSet

func tidy() -> bool:
	if complete:
		return false
	
	complete = true
	queue_free()
	return true


func activate():
	if tidy():
		trigger.emit()

