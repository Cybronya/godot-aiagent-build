# Source:  https://github.com/crystal-bit/godot-game-template/blob/main/addons/ggt-core/transitions/progress.gd
# Repo:    crystal-bit/godot-game-template (star 993) | License: MIT | Collected: 2026-10-29
# Commit:  e9dc8926d156
extends Control

@onready var bar := $ProgressBar


func is_completed():
	return bar.value == bar.max_value
