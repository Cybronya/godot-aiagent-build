# Source:  https://github.com/crystal-bit/godot-game-template/blob/main/scenes/menu/game_version.gd
# Repo:    crystal-bit/godot-game-template (star 993) | License: MIT | Collected: 2026-10-29
# Commit:  e9dc8926d156
extends Label


func _ready():
	# you need to enable "Advanced Settings" to make this property visible
	var ver = ProjectSettings.get_setting("application/config/version")
	var mode = "debug" if OS.is_debug_build() else "release"
	text =  "%s (%s)" % [ver, mode]
