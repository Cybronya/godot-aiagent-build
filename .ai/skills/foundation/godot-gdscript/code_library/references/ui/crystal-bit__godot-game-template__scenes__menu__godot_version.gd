# Source:  https://github.com/crystal-bit/godot-game-template/blob/main/scenes/menu/godot_version.gd
# Repo:    crystal-bit/godot-game-template (star 993) | License: MIT | Collected: 2026-10-29
# Commit:  e9dc8926d156
extends Label


func _ready():
	if OS.has_feature('release'):
		queue_free()
	else:
		text = "Godot %s" % Engine.get_version_info().string
