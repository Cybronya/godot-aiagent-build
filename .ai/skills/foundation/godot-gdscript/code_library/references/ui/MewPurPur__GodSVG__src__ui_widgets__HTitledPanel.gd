# Source:  https://github.com/MewPurPur/GodSVG/blob/main/src/ui_widgets/HTitledPanel.gd
# Repo:    MewPurPur/GodSVG (star 2784) | License: MIT | Collected: 2026-10-28
# Commit:  52ad7944fcf9
@icon("res://no_export/class_icons/HTitledPanel.svg")
class_name HTitledPanel extends TitledPanel

func _get_minimum_size() -> Vector2:
	return _get_minimum_size_common_logic(false)

func _notification(what: int) -> void:
	_notification_common_logic(what, false)
