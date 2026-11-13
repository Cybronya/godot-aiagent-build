# Source:  https://github.com/bitbrain/godot-gamejam/blob/main/godot/ui/components/float_range_game_settings_option.gd
# Repo:    bitbrain/godot-gamejam (star 815) | License: MIT | Collected: 2026-10-31
# Commit:  159f2c47196a
extends HSlider

@export var property:String = ""

var initialised = false

func _ready():
	value = UserSettings.get_value(property)

func _on_float_range_game_settings_option_value_changed(val):
	if !initialised:
		initialised = true
	UserSettings.set_value(property, val)
