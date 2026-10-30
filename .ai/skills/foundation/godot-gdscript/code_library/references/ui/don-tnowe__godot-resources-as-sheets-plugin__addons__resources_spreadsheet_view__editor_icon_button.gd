# Source:  https://github.com/don-tnowe/godot-resources-as-sheets-plugin/blob/master/addons/resources_spreadsheet_view/editor_icon_button.gd
# Repo:    don-tnowe/godot-resources-as-sheets-plugin (star 1031) | License: MIT | Collected: 2026-10-29
# Commit:  3363e0d2136c
@tool
extends Button

@export var icon_name := "Node" :
	set(v):
		icon_name = v
		if has_theme_icon(v, "EditorIcons"):
			icon = get_theme_icon(v, "EditorIcons")


func _ready():
	self.icon_name = (icon_name)
