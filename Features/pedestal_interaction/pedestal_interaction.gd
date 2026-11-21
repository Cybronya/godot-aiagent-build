class_name PedestalInteraction
extends Node
## 交互底座：管理物品放置/移除，追踪正确性，支持多底座谜题组。
##
## 抽象自 gdquest-demos/godot-open-rpg (MIT)，简化：
## - 去掉 Dialogic/Inventory 依赖，用通用 item_id 接口
## - 保留核心概念：期望物品 + 放置/移除 + 状态追踪 + 谜题组
## - 信号驱动：item_placed / item_removed / state_changed / puzzle_solved
## - 谜题组全对时自动禁用所有成员并发射 puzzle_solved

signal item_placed(item_id: int)
signal item_removed()
signal state_changed(is_correct: bool)
signal puzzle_solved()

@export var expected_item_id: int = -1

var current_item_id: int = -1
var is_active: bool = true
var _is_correct: bool = false

static var _groups: Dictionary = {}


func _ready() -> void:
	_update_correctness()


## 放置物品到底座。item_id 为物品类型标识（>=0 有效）。
func place_item(item_id: int) -> void:
	current_item_id = item_id
	_update_correctness()
	item_placed.emit(item_id)
	state_changed.emit(_is_correct)
	if _is_correct:
		_check_groups()


## 移除底座上的物品。
func remove_item() -> void:
	current_item_id = -1
	_update_correctness()
	item_removed.emit()
	state_changed.emit(_is_correct)


func _update_correctness() -> void:
	_is_correct = current_item_id == expected_item_id and current_item_id >= 0


func is_correct() -> bool:
	return _is_correct


## 加入谜题组。不立即检查——只在 place_item 变正确时触发检查。
func join_puzzle_group(group_name: String) -> void:
	if not _groups.has(group_name):
		_groups[group_name] = []
	_groups[group_name].append(self)


func leave_puzzle_group(group_name: String) -> void:
	if _groups.has(group_name):
		_groups[group_name].erase(self)


func _check_groups() -> void:
	for group_name in _groups:
		var members: Array = _groups[group_name]
		if members.is_empty():
			continue
		var all_correct := true
		for m in members:
			if not m.is_correct():
				all_correct = false
				break
		if all_correct:
			puzzle_solved.emit()
			for m in members:
				m.is_active = false
