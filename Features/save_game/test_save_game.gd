extends SceneTree
## SaveGame 组件自身验证：槽位落盘、槽位列表与最近槽位、玩家/serializable 数据
## 往返、删除节点恢复、instanced 重建、非法输入防护。
##
## 用法：godot --headless --path . -s res://Features/save_game/test_save_game.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const SCENE_PATH := "res://Features/save_game/SaveGame.tscn"
const SLOT := "t_save_game_a"

var _failures: PackedStringArray = []
var _saved_events := 0
var _loaded_events := 0


class PlayerStub extends Node:
	var hp := 5
	var load_calls := 0

	func _init() -> void:
		add_to_group("player")

	func get_save_data() -> Dictionary:
		return {"hp": hp}

	func load_save_data(data: Dictionary) -> void:
		load_calls += 1
		hp = data.get("hp", 0)


class StaticStub extends Node:
	var opened := false
	var load_calls := 0

	func _init() -> void:
		add_to_group("serializable")

	func get_save_data() -> Dictionary:
		return {"opened": opened}

	func load_save_data(data: Dictionary) -> void:
		load_calls += 1
		opened = data.get("opened", false)


func _initialize() -> void:
	var packed: PackedScene = load(SCENE_PATH)
	if packed == null:
		_failures.append("加载 %s 失败" % SCENE_PATH)
		_report()
		return
	var saver: SaveGame = packed.instantiate()
	saver.game_saved.connect(func(_p: String) -> void: _saved_events += 1)
	saver.game_loaded.connect(func(_d: SaveData) -> void: _loaded_events += 1)
	root.add_child(saver)
	await process_frame
	await _run(saver)
	_report()


func _run(saver: SaveGame) -> void:
	# 搭一个假当前场景：world(player + door + doomed)
	var world := Node.new()
	world.name = "TestWorld"
	var player := PlayerStub.new()
	player.name = "Player"
	var door := StaticStub.new()
	door.name = "Door"
	door.opened = true
	var doomed := StaticStub.new()
	doomed.name = "Doomed"
	world.add_child(player)
	world.add_child(door)
	world.add_child(doomed)
	root.add_child(world)
	current_scene = world

	# 1. 非法槽位名防护
	if saver.save_to_slot("") or saver.save_to_slot("a/b"):
		_failures.append("空名/含路径分隔符的槽位名应被拒绝")

	# 2. instanced 协议：一个已销毁的实例化节点（带 instance_uid 数据）
	var instanced_stub := Node.new()
	instanced_stub.set_script(load("res://Features/save_game/instanced_node_fixture.gd"))
	instanced_stub.name = "DroppedGem"
	instanced_stub.add_to_group("serializable")
	instanced_stub.stored_value = 42
	world.add_child(instanced_stub)

	# 3. 删除节点记账 + 落盘
	saver.add_deleted_node_path(String(doomed.get_path()))
	world.remove_child(doomed)
	doomed.free()
	if not saver.save_to_slot(SLOT):
		_failures.append("save_to_slot 应返回 true")
	if _saved_events != 1:
		_failures.append("game_saved 应触发 1 次，实际 %d" % _saved_events)
	var slot_path := "user://saved_games/%s.save" % SLOT
	if not FileAccess.file_exists(slot_path):
		_failures.append("槽位文件应存在: " + slot_path)

	# 4. 槽位查询
	if not saver.get_slot_list().has(SLOT):
		_failures.append("get_slot_list 应包含 %s" % SLOT)
	if saver.get_last_slot() != SLOT:
		_failures.append("get_last_slot 应为 %s，实际 %s" % [SLOT, saver.get_last_slot()])

	# 5. 破坏现场后恢复
	player.hp = 1
	door.opened = false
	var world_stub := StaticStub.new()  # 占位同名节点，模拟重开后静态结构重建
	world_stub.name = "Doomed"
	world.add_child(world_stub)
	if not saver.load_from_slot(SLOT):
		_failures.append("load_from_slot 应返回 true")
	await process_frame
	await process_frame
	if _loaded_events != 1:
		_failures.append("game_loaded 应触发 1 次，实际 %d" % _loaded_events)
	if player.load_calls != 1 or player.hp != 5:
		_failures.append("玩家数据应恢复 hp=5（实际 hp=%d, load_calls=%d）" % [player.hp, player.load_calls])
	if door.opened != true:
		_failures.append("serializable 数据应恢复 opened=true")
	if is_instance_valid(world_stub) and not world_stub.is_queued_for_deletion():
		_failures.append("删除记账节点 Doomed 应在恢复时被 queue_free")
	var rebuilt: Node = null
	for child in root.get_children():
		if child.is_in_group("instanced"):
			rebuilt = child
	if rebuilt == null:
		_failures.append("instanced 节点应在恢复时重建")
	elif rebuilt.stored_value != 42:
		_failures.append("instanced 节点数据应恢复 value=42，实际 %s" % rebuilt.stored_value)

	# 6. 读取不存在的槽位
	if saver.load_from_slot("no_such_slot_xyz"):
		_failures.append("读取不存在槽位应返回 false")

	# 清理测试槽位
	DirAccess.remove_absolute(slot_path)
	DirAccess.remove_absolute("user://saved_games/_last.txt")


func _report() -> void:
	if _failures.is_empty():
		print("PASS: SaveGame 组件验证通过")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
