# Source:  https://github.com/Maaack/Godot-Game-Template/blob/main/addons/maaacks_game_template/base/nodes/labels/config_name_label.gd
# Repo:    Maaack/Godot-Game-Template (star 1709) | License: MIT | Collected: 2026-10-26
# Commit:  5cc611f7dfcd
@tool
extends Label
## Displays the value of `application/config/name`, set in project settings.

const NO_NAME_STRING : String = "Title"

## If true, update the title when ready.
@export var auto_update : bool = true

func update_name_label():
	var config_name : String = ProjectSettings.get_setting("application/config/name", NO_NAME_STRING)
	if config_name.is_empty():
		config_name = NO_NAME_STRING
	text = config_name

func _ready():
	if auto_update:
		update_name_label()
