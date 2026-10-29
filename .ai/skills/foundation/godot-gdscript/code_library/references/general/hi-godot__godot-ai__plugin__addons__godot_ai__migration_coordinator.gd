# Source:  https://github.com/hi-godot/godot-ai/blob/main/plugin/addons/godot_ai/migration_coordinator.gd
# Repo:    hi-godot/godot-ai (star 3268) | License: MIT | Collected: 2026-10-29
# Commit:  a799acfa49cd
@tool
extends Node

## Compatibility path for cached capsule dependencies after a signed update.
## The canonical plugin has no remaining capsule installation to coordinate.
const STATUS_SETTING := "godot_ai/v4_migration_bridge_status"


func start(_package: Dictionary) -> void:
	queue_free()


static func record_status(error: String) -> void:
	var settings := EditorInterface.get_editor_settings()
	if settings != null:
		settings.set_setting(status_setting(), JSON.stringify({"error": error}))


static func status_setting() -> String:
	return STATUS_SETTING + "_" + ProjectSettings.globalize_path("res://").sha256_text()
