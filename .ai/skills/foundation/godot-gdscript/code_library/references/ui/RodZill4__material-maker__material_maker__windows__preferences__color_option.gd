# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/windows/preferences/color_option.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
class_name ColorOption
extends ColorPickerButton

@export var config_variable : String

func _ready() -> void:
	get_popup().about_to_popup.connect(_picker_about_to_popup)

func _picker_about_to_popup() -> void:
	get_popup().content_scale_factor = mm_globals.ui_scale_factor()

func init_from_config(config : ConfigFile) -> void:
	if config.has_section_key("config", config_variable):
		color = config.get_value("config", config_variable)

func update_config(config : ConfigFile) -> void:
	config.set_value("config", config_variable, color)
