# Source:  https://github.com/j-p-higgins/SoundThread/blob/main/scenes/main/scripts/help_window.gd
# Repo:    j-p-higgins/SoundThread (star 3260) | License: MIT | Collected: 2026-10-29
# Commit:  a33198a84fa4
extends Window


func _ready():
	pass


func _on_close_requested() -> void:
	queue_free()
