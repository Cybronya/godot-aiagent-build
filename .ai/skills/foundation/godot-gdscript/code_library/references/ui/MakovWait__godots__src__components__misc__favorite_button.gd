# Source:  https://github.com/MakovWait/godots/blob/main/src/components/misc/favorite_button.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
extends TextureButton


func _ready() -> void:
#	texture_normal = get_theme_icon("NonFavorite", "EditorIcons")
#	texture_pressed = get_theme_icon("Favorites", "EditorIcons")
	
	texture_normal = get_theme_icon("Favorites", "EditorIcons")
	toggle_mode = true

	_update_modualate()
	toggled.connect(func(_arg: bool) -> void: _update_modualate())


func _update_modualate() -> void:
	modulate = Color(1, 1, 1, 1) if button_pressed else Color(1, 1, 1, 0.2)
