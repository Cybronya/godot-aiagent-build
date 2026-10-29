# Source:  https://github.com/hi-godot/godot-ai/blob/main/plugin/addons/godot_ai/migration_fallback.gd
# Repo:    hi-godot/godot-ai (star 3268) | License: MIT | Collected: 2026-10-29
# Commit:  a799acfa49cd
@tool
extends Node

## Retained capsule dependency path. The canonical v4 tree has no embedded
## v3 fallback; keeping this path must never initiate a downgrade.
static func available() -> bool:
	return false


func start() -> void:
	queue_free()
