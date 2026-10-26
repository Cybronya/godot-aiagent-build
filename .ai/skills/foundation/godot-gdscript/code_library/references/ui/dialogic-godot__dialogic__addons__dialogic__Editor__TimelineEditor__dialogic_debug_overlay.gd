# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Editor/TimelineEditor/dialogic_debug_overlay.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  main
extends CanvasLayer

var settings := {}


func _init() -> void:
	settings.merge(DialogicUtil.get_editor_setting("debug_settings", {}), true)


func _ready() -> void:
	visible = settings.get("debug_visible", false)


func _input(event: InputEvent) -> void:
	if event.is_pressed() and (Input.is_key_pressed(KEY_CTRL) or Input.is_key_pressed(KEY_META)) and Input.is_key_pressed(KEY_D) and Input.is_key_pressed(KEY_SPACE):
		visible = not visible
		settings["debug_visible"] = visible
		save()


func save() -> void:
	DialogicUtil.set_editor_setting("debug_settings", settings)
