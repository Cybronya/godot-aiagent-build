# Source:  https://github.com/j-p-higgins/SoundThread/blob/main/scenes/main/scripts/color_rect_theme_invert.gd
# Repo:    j-p-higgins/SoundThread (star 3260) | License: MIT | Collected: 2026-10-29
# Commit:  a33198a84fa4
extends ColorRect


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	var interface_settings = ConfigHandler.load_interface_settings()
	#check if the theme is inverted
	if interface_settings.invert_theme:
		color = Color(0.898, 0.898, 0.898, 0.6)
	else:
		color = Color(0.102, 0.102, 0.102, 0.6)
