# Source:  https://github.com/crystal-bit/godot-game-template/blob/main/addons/ggt-core/scenes/scenes-history.gd
# Repo:    crystal-bit/godot-game-template (star 993) | License: MIT | Collected: 2026-10-29
# Commit:  e9dc8926d156
extends RefCounted

const config = preload("res://addons/ggt-core/config.tres")
var _history: Array[GGT_SceneData] = []


func add(scene_path: String, params = null):
	var data = GGT_SceneData.new()
	data.path = scene_path
	data.params = params
	_history.push_front(data)
	while _history.size() > config.max_history_length:
		_history.pop_back()


func get_last_loaded_scene_data() -> GGT_SceneData:
	if _history.size() == 0:
		return null
	return _history[0]
