# Source:  https://github.com/RodZill4/material-maker/blob/master/material_maker/windows/progress_window/progress_window.gd
# Repo:    RodZill4/material-maker (star 6030) | License: MIT | Collected: 2026-10-28
# Commit:  master
extends Popup

func _ready() -> void:
	content_scale_factor = mm_globals.ui_scale_factor()
	theme = mm_globals.main_window.theme
	popup_centered()

func set_text(t) -> void:
	$PanelContainer/MarginContainer/VBoxContainer/Step.text = t

func set_progress(p) -> void:
	$PanelContainer/MarginContainer/VBoxContainer/ProgressBar.value = p * 100.0
