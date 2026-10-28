# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/panels/graph_edit/graph_align_menu.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends PanelContainer

func _on_align_start_pressed() -> void:
	mm_globals.main_window.edit_align_start()

func _on_align_end_pressed() -> void:
	mm_globals.main_window.edit_align_end()

func _on_align_top_pressed() -> void:
	mm_globals.main_window.edit_align_top()

func _on_straighten_pressed() -> void:
	mm_globals.main_window.edit_straighten_connections()
