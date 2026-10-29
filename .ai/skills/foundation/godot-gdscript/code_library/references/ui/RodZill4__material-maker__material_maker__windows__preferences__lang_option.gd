# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/windows/preferences/lang_option.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  7d6daae3c74c
extends OptionButton

@export var config_variable : String

var locales : Array = []

func _ready() -> void:
	init_from_locales()

func init_from_locales():
	locales = TranslationServer.get_loaded_locales()
	locales.insert(0, "en")
	clear()
	for l in locales:
		add_item(l+" - "+TranslationServer.get_locale_name(l))

func init_from_config(config : ConfigFile) -> void:
	if config.has_section_key("config", config_variable):
		selected = locales.find(config.get_value("config", config_variable))
	if selected == -1:
		selected = 0

func update_config(config : ConfigFile) -> void:
	config.set_value("config", config_variable, locales[selected])
