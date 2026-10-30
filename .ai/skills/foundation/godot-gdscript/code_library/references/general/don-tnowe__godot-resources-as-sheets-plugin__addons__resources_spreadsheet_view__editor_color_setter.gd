# Source:  https://github.com/don-tnowe/godot-resources-as-sheets-plugin/blob/master/addons/resources_spreadsheet_view/editor_color_setter.gd
# Repo:    don-tnowe/godot-resources-as-sheets-plugin (star 1031) | License: MIT | Collected: 2026-10-29
# Commit:  3363e0d2136c
@tool
extends Control


func _ready():
	modulate = get_theme_color("accent_color", "Editor")
