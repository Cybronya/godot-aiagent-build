# Source:  https://github.com/TheDuckCow/godot-road-generator/blob/main/road_demos/demo_resources/demo_ui_common.gd
# Repo:    TheDuckCow/godot-road-generator (star 1249) | License: MIT | Collected: 2026-10-29
# Commit:  7cbefde04e57
extends Control

const MAIN_SCENE := "res://road_demos/demo_menu.tscn"

@onready var back: Button = %Back

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action("ui_cancel") and event.is_released():
		var focus_owner = get_viewport().gui_get_focus_owner()
		get_viewport().set_input_as_handled()
		if focus_owner == back:
			_on_back_pressed()
		else:
			back.grab_focus()


func _on_back_pressed() -> void:
	var error = get_tree().change_scene_to_file(MAIN_SCENE)
	if error != OK:
		print("Failed to change scene: ", error)


func _on_reload_pressed() -> void:
	get_tree().reload_current_scene()
