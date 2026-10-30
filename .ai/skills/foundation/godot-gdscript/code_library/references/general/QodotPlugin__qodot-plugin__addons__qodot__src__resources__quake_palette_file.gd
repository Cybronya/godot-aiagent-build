# Source:  https://github.com/QodotPlugin/qodot-plugin/blob/master/addons/qodot/src/resources/quake_palette_file.gd
# Repo:    QodotPlugin/qodot-plugin (star 982) | License: MIT | Collected: 2026-10-29
# Commit:  4731a36dec69
class_name QuakePaletteFile
extends Resource

export(PoolColorArray) var colors : PoolColorArray

func _init(colors) -> void:
	self.colors = colors
