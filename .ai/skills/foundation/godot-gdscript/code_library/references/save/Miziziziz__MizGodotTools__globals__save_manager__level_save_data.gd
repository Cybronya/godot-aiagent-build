# Source:  https://github.com/Miziziziz/MizGodotTools/blob/main/globals/save_manager/level_save_data.gd
# Repo:    Miziziziz/MizGodotTools (star 987) | License: MIT | Collected: 2026-10-29
# Commit:  cb548f9035a3
class_name LevelSaveData extends Node


var saved_nodes : Array = [] # array of saved nodes data
var deleted_node_paths : Array[String] = [] # array of paths of deleted nodes in this scene

func get_level_save_data_as_dict() -> Dictionary:
	return {
		"saved_nodes" : saved_nodes,
		"deleted_node_paths" : deleted_node_paths,
	}
