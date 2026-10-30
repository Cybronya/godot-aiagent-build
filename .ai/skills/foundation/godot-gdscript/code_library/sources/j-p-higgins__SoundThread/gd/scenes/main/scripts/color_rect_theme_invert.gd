extends ColorRect


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	var interface_settings = ConfigHandler.load_interface_settings()
	#check if the theme is inverted
	if interface_settings.invert_theme:
		color = Color(0.898, 0.898, 0.898, 0.6)
	else:
		color = Color(0.102, 0.102, 0.102, 0.6)
