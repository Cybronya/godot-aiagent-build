# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/windows/preferences/bool_option.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
extends CheckBox

class_name BoolOption

@export var config_variable : String

func _ready() -> void:
	pass

func init_from_config(config : ConfigFile) -> void:
	if config.has_section_key("config", config_variable):
		button_pressed = config.get_value("config", config_variable)

func update_config(config : ConfigFile) -> void:
	config.set_value("config", config_variable, button_pressed)
