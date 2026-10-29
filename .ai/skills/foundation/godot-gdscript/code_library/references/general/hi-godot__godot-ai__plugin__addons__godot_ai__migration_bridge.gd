# Source:  https://github.com/hi-godot/godot-ai/blob/main/plugin/addons/godot_ai/migration_bridge.gd
# Repo:    hi-godot/godot-ai (star 3268) | License: MIT | Collected: 2026-10-29
# Commit:  a799acfa49cd
@tool
extends Node

## Retained capsule path: Godot can finish an old parser's dependency list
## while loading the new plugin. Migration is complete in the canonical tree;
## the verified capsule carries the active implementation at this same path.
func start() -> void:
	queue_free()
