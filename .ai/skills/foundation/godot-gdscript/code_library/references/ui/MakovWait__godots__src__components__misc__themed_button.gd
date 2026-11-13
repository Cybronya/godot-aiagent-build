# Source:  https://github.com/MakovWait/godots/blob/main/src/components/misc/themed_button.gd
# Repo:    MakovWait/godots (star 816) | License: MIT | Collected: 2026-10-31
# Commit:  8e4eb2baa050
extends Button


@export var _theme_icon_name := "Load"
@export var _theme_type := "EditorIcons"


func _ready() -> void:
	_update_theme()
	theme_changed.connect(_update_theme)


func _update_theme() -> void:
	icon = get_theme_icon(_theme_icon_name, _theme_type)
