# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/windows/preferences/float_option.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
extends "res://material_maker/widgets/float_edit/float_edit.gd"

class_name FloatOption

@export var config_variable : String

func _ready() -> void:
	pass

func init_from_config(config : ConfigFile) -> void:
	if config.has_section_key("config", config_variable):
		set_value(config.get_value("config", config_variable))

func update_config(config : ConfigFile) -> void:
	config.set_value("config", config_variable, get_value())
