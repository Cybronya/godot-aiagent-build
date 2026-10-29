# Source:  https://github.com/Arnklit/Waterways/blob/main/addons/waterways/progress_window.gd
# Repo:    Arnklit/Waterways (star 1342) | License: MIT | Collected: 2026-10-29
# Commit:  cd2e2193fe2c
# Copyright © 2021 Kasper Arnklit Frandsen - MIT License
# See `LICENSE.md` included in the source distribution for details.
tool
extends Control


onready var _progress_bar = $VBoxContainer/ProgressBar


func show_progress(message, progress) -> void:
	self.window_title = message
	_progress_bar.ratio = progress
