# Source:  https://github.com/dialogic-godot/dialogic/blob/main/addons/dialogic/Modules/StyleEditor/Components/style_browser_window.gd
# Repo:    dialogic-godot/dialogic (star 6121) | License: MIT | Collected: 2026-10-26
# Commit:  701b67bbe601
@tool
extends Window

var info := {}
signal part_selected(info:Dictionary)


func _on_close_requested() -> void:
	info = {}
	part_selected.emit({})
	hide()


func get_picked_info() -> Dictionary:
	await part_selected
	return info


func _on_style_browser_activate_part(part_info: Dictionary) -> void:
	info = part_info
	part_selected.emit(part_info)
	hide()
