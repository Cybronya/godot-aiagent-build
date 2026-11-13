# Source:  https://github.com/cis-ash/TEXTREME/blob/master/Scenes/Main/FontManager.gd
# Repo:    cis-ash/TEXTREME (star 801) | License: MIT | Collected: 2026-10-31
# Commit:  673dc09d9132
extends Node

signal font_size_changed

export var editor_font : DynamicFont = null
export var step_size := 12
export var max_size := 36
export var min_size := 12

func increase_editor_font():
	if editor_font != null:
		if editor_font.size + step_size <= max_size:
			editor_font.size += step_size
			editor_font.update_changes()
		
	get_tree().call_group("editor_font_users", "update_editor_font_parameters")

func decrease_editor_font():
	if editor_font != null:
		if editor_font.size - step_size >= min_size:
			editor_font.size -= step_size
			editor_font.update_changes()
		
	get_tree().call_group("editor_font_users", "update_editor_font_parameters")
