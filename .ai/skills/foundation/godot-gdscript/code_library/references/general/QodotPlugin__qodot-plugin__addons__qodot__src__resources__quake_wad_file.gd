# Source:  https://github.com/QodotPlugin/qodot-plugin/blob/master/addons/qodot/src/resources/quake_wad_file.gd
# Repo:    QodotPlugin/qodot-plugin (star 982) | License: MIT | Collected: 2026-10-29
# Commit:  4731a36dec69
class_name QuakeWadFile
extends Resource

export(Dictionary) var textures : Dictionary

func _init(textures: Dictionary) -> void:
	self.textures = textures
