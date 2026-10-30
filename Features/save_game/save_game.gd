class_name SaveGame
extends Node
## 槽位存档组件：收集世界状态快照到槽位文件，或把槽位快照应用回当前场景树。
##
## 节点存档协议（节点按需实现两个方法即可参与存档）：
## - get_save_data() -> Dictionary：保存时收集；
## - load_save_data(data: Dictionary)：恢复时回填。
## 组约定：
## - "player"：全局玩家实体（数据存入 player_data，独立于场景快照）；
## - "serializable"：场景静态可存档节点（以 node_path 记账，如门、开关）；
## - "instanced"：运行时实例化的可存档节点（以 instance_uid 记账，如掉落物；
##   其 get_save_data() 须自带 instance_uid 字段指向可实例化的场景路径）。
##
## 职责边界：本组件只负责「快照收集 / 落盘 / 应用回当前场景树」。
## 跨场景切换（change_scene + 重放快照）由组合层编排：先切场景，再 load_from_slot。
## 快捷键、自动触发节奏、UI 都不属于本组件。
##
## 抽象来源片段：Miziziziz/MizGodotTools globals/save_manager（MIT），
## 剥除 autoload / 输入快捷键 / LevelManager 耦合；合并 GameSaveData + LevelSaveData；
## 场景切换职责移交组合层，使组件可在纯测试环境验证。

signal game_saved(slot_path: String)
signal game_loaded(save_data: SaveData)

const SAVE_DIRECTORY := "user://saved_games/"
const SAVE_SUFFIX := ".save"
const SLOT_PATH_FORMAT := "user://saved_games/%s.save"
const LAST_SLOT_FILE := "user://saved_games/_last.txt"

@export var verbose := false

var _deleted_node_paths: Array[String] = []


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(SAVE_DIRECTORY)


# ─────────────────────── 保存 ───────────────────────

## 保存到指定槽位。slot_name 为空或含非法字符时拒绝并返回 false。
func save_to_slot(slot_name: String) -> bool:
	if not _is_valid_slot_name(slot_name):
		push_error("SaveGame: 非法槽位名 \"%s\"" % slot_name)
		return false
	var slot_path := SLOT_PATH_FORMAT % slot_name
	var data := _collect_save_data()
	if not data.write_to_file(slot_path):
		return false
	_record_last_slot(slot_path)
	_log("已保存 " + slot_path)
	game_saved.emit(slot_path)
	return true


func autosave() -> bool:
	return save_to_slot("autosave")


func quicksave() -> bool:
	return save_to_slot("quicksave")


func _collect_save_data() -> SaveData:
	var data := SaveData.new()
	var current_scene := get_tree().current_scene
	if current_scene != null:
		data.last_scene_path = current_scene.scene_file_path
	var player := get_tree().get_first_node_in_group("player")
	if player != null and player.has_method("get_save_data"):
		data.player_data = player.get_save_data()
	var saved_nodes: Array = []
	for node in get_tree().get_nodes_in_group("serializable"):
		if not node.has_method("get_save_data"):
			continue
		var node_data: Dictionary = node.get_save_data()
		if not node_data.has(SaveData.INSTANCE_UID_KEY):
			node_data[SaveData.NODE_PATH_KEY] = String(node.get_path())
		saved_nodes.append(node_data)
	data.store_scene_data(data.last_scene_path, saved_nodes, _deleted_node_paths.duplicate())
	return data


## 记录静态节点被删除（如道具被拾取）；下次保存时写入快照，恢复时按路径清除。
func add_deleted_node_path(node_path: String) -> void:
	_deleted_node_paths.append(node_path)


# ─────────────────────── 读取 ───────────────────────

## 把槽位快照应用回当前场景树：清理 instanced、按记录删除节点、
## 回填 serializable 数据、重建 instanced。不负责场景切换。
func load_from_slot(slot_name: String) -> bool:
	if not _is_valid_slot_name(slot_name):
		push_error("SaveGame: 非法槽位名 \"%s\"" % slot_name)
		return false
	var data := SaveData.read_from_file(SLOT_PATH_FORMAT % slot_name)
	if data == null:
		return false
	_record_last_slot(SLOT_PATH_FORMAT % slot_name)
	var scene_path := data.last_scene_path
	if get_tree().current_scene != null:
		scene_path = get_tree().current_scene.scene_file_path
	get_tree().call_group("instanced", "free")
	var player := get_tree().get_first_node_in_group("player")
	if player != null and player.has_method("load_save_data"):
		player.load_save_data(data.player_data)
	for node_path in data.get_deleted_node_paths(scene_path):
		var node := get_node_or_null(node_path)
		if node == null:
			_log("待删除节点不在场景中，跳过: " + node_path)
			continue
		node.queue_free()
	for node_data in data.get_saved_nodes(scene_path):
		_restore_node(node_data)
	_log("已恢复 " + slot_name)
	game_loaded.emit(data)
	return true


func _restore_node(node_data: Dictionary) -> void:
	if node_data.has(SaveData.INSTANCE_UID_KEY):
		var packed: PackedScene = load(node_data[SaveData.INSTANCE_UID_KEY])
		if packed == null:
			push_warning("SaveGame: instance_uid 无法加载 " + str(node_data.get(SaveData.INSTANCE_UID_KEY)))
			return
		var instance: Node = packed.instantiate()
		instance.add_to_group("instanced")
		get_tree().root.add_child.call_deferred(instance)
		instance.load_save_data.call_deferred(node_data)
	elif node_data.has(SaveData.NODE_PATH_KEY):
		var node := get_node_or_null(node_data[SaveData.NODE_PATH_KEY])
		if node == null:
			_log("快照节点不在场景中，跳过: " + str(node_data[SaveData.NODE_PATH_KEY]))
			return
		if node.has_method("load_save_data"):
			node.load_save_data(node_data)
	else:
		push_warning("SaveGame: 快照缺 node_path/instance_uid，丢弃 " + str(node_data))


func load_quicksave() -> bool:
	return load_from_slot("quicksave")


func load_autosave() -> bool:
	return load_from_slot("autosave")


# ─────────────────────── 查询 ───────────────────────

## 全部槽位名（不含扩展名），按修改时间新 → 旧排序。
func get_slot_list() -> Array[String]:
	var slots: Array[String] = []
	var dir := DirAccess.open(SAVE_DIRECTORY)
	if dir == null:
		return slots
	dir.list_dir_begin()
	var file_name := dir.get_next()
	while file_name != "":
		if not dir.current_is_dir() and file_name.ends_with(SAVE_SUFFIX) \
				and not file_name.begins_with("_"):
			slots.append(file_name.trim_suffix(SAVE_SUFFIX))
		file_name = dir.get_next()
	slots.sort_custom(func(a: String, b: String) -> bool:
		var path_a := SLOT_PATH_FORMAT % a
		var path_b := SLOT_PATH_FORMAT % b
		return FileAccess.get_modified_time(path_a) > FileAccess.get_modified_time(path_b))
	return slots


## 最近一次写入的槽位名；从未保存过返回 ""。
func get_last_slot() -> String:
	if not FileAccess.file_exists(LAST_SLOT_FILE):
		return ""
	var file := FileAccess.open(LAST_SLOT_FILE, FileAccess.READ)
	var line := file.get_line().strip_edges()
	file.close()
	if line.is_empty() or not FileAccess.file_exists(line):
		return ""
	return line.trim_prefix(SAVE_DIRECTORY).trim_suffix(SAVE_SUFFIX)


func _record_last_slot(slot_path: String) -> void:
	var file := FileAccess.open(LAST_SLOT_FILE, FileAccess.WRITE)
	if file != null:
		file.store_line(slot_path)


func _is_valid_slot_name(slot_name: String) -> bool:
	if slot_name.is_empty():
		return false
	for ch in "/\\:*?\"<>|%":
		if slot_name.contains(ch):
			return false
	return true


func _log(message: String) -> void:
	if verbose:
		print("SaveGame: ", message)
