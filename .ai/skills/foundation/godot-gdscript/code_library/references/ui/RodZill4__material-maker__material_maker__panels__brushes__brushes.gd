# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/panels/brushes/brushes.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends "res://material_maker/panels/library/library.gd"

func _ready():
	super._ready()

func _on_Tree_item_activated():
	var main_window = mm_globals.main_window
	var data = %Tree.get_selected().get_metadata(0)
	if data != null:
		main_window.get_current_project().set_brush(data)

func _on_GetFromWebsite_pressed():
	var project_panel = mm_globals.main_window.get_current_project()
	if not project_panel.has_method("set_brush"):
		return
	var dialog = load("res://material_maker/windows/load_from_website/load_from_website.tscn").instantiate()
	var result : Dictionary = await dialog.select_asset(1)
	if result != {}:
		project_panel.set_brush(result)
