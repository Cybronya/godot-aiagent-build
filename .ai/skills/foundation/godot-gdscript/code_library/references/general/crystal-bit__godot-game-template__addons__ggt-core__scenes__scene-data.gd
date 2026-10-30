# Source:  https://github.com/crystal-bit/godot-game-template/blob/main/addons/ggt-core/scenes/scene-data.gd
# Repo:    crystal-bit/godot-game-template (star 993) | License: MIT | Collected: 2026-10-29
# Commit:  e9dc8926d156
class_name GGT_SceneData
extends RefCounted

var path: String = ""
var params = null


func _to_string():
	return path + " | params: " + str(params)
