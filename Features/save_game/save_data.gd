class_name SaveData
extends RefCounted
## 存档数据容器：一次存档 = 上次场景路径 + 玩家数据 + 每个场景的节点快照。
##
## 每个场景的数据含两份内容：
## - saved_nodes：serializable/instanced 节点的 get_save_data() 字典数组；
## - deleted_node_paths：运行期间被删除的静态节点路径（如已拾取的道具）。
##
## 序列化走 JSON（FileAccess 文本），字段结构自描述、可人工检查。
## 抽象来源片段：Miziziziz/MizGodotTools globals/save_manager（MIT），
## 合并原 GameSaveData + LevelSaveData 两类为单类，剥除 autoload 依赖。

const NODE_PATH_KEY := "node_path"
const INSTANCE_UID_KEY := "instance_uid"

var last_scene_path := ""
var player_data := {}

var _scene_data := {}  # scene_path -> {"saved_nodes": Array, "deleted_node_paths": Array}


func get_saved_nodes(scene_path: String) -> Array:
	var entry: Dictionary = _scene_data.get(scene_path, {})
	return entry.get("saved_nodes", [])


func get_deleted_node_paths(scene_path: String) -> Array:
	var entry: Dictionary = _scene_data.get(scene_path, {})
	return entry.get("deleted_node_paths", [])


func store_scene_data(scene_path: String, saved_nodes: Array, deleted_node_paths: Array) -> void:
	_scene_data[scene_path] = {
		"saved_nodes": saved_nodes,
		"deleted_node_paths": deleted_node_paths,
	}


func to_dict() -> Dictionary:
	return {
		"last_scene_path": last_scene_path,
		"player_data": player_data,
		"scene_data": _scene_data,
	}


static func from_dict(data: Dictionary) -> SaveData:
	var save := SaveData.new()
	if data.has("last_scene_path"):
		save.last_scene_path = data.last_scene_path
	if data.has("player_data"):
		save.player_data = data.player_data
	if data.has("scene_data"):
		save._scene_data = data.scene_data
	return save


func write_to_file(file_path: String) -> bool:
	var file := FileAccess.open(file_path, FileAccess.WRITE)
	if file == null:
		push_error("SaveData: 无法写入 %s（%d）" % [file_path, FileAccess.get_open_error()])
		return false
	file.store_string(JSON.stringify(to_dict()))
	file.close()
	return true


static func read_from_file(file_path: String) -> SaveData:
	if not FileAccess.file_exists(file_path):
		push_warning("SaveData: 存档不存在 %s" % file_path)
		return null
	var file := FileAccess.open(file_path, FileAccess.READ)
	var parsed = JSON.parse_string(file.get_as_text())
	file.close()
	if parsed is Dictionary:
		return from_dict(parsed)
	push_error("SaveData: 解析失败（非法 JSON）%s" % file_path)
	return null
