# Source:  https://github.com/Miziziziz/MizGodotTools/blob/main/example_scenes/settings_and_ui_sounds_example/settings_example.gd
# Repo:    Miziziziz/MizGodotTools (star 987) | License: MIT | Collected: 2026-10-29
# Commit:  cb548f9035a3
extends Control

@onready var settings_menu: Control = $SettingsMenu
@onready var open_settings_button: Button = $OpenSettingsButton

func _ready():
	open_settings_button.button_up.connect(settings_menu.show)
	open_settings_button.button_up.connect(open_settings_button.hide)
	
	settings_menu.back_button.button_up.connect(open_settings_button.show)
	settings_menu.back_button.button_up.connect(settings_menu.hide)
