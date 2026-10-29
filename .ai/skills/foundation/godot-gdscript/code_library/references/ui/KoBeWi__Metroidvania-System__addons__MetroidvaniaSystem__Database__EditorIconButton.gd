# Source:  https://github.com/KoBeWi/Metroidvania-System/blob/master/addons/MetroidvaniaSystem/Database/EditorIconButton.gd
# Repo:    KoBeWi/Metroidvania-System (star 1596) | License: MIT | Collected: 2026-10-26
# Commit:  0065ae897429
@tool
extends Button

@export var icon_name: String

func _notification(what: int) -> void:
	if what == NOTIFICATION_THEME_CHANGED and not is_part_of_edited_scene():
		icon = get_theme_icon(icon_name, &"EditorIcons")
