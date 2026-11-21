class_name Blackboard
extends Node
## 行为树黑板：存储多个命名数据表，行为树节点间共享数据。
##
## 抽象自 bitbrain/beehave (MIT)，简化：
## - 去掉调试数据消毒逻辑（依赖特定调试器连接）
## - 保留多命名黑板 + set/get/has/erase API
## - setter duplicate 防止引用共享
## - 实例隔离：每个节点独立存储

const DEFAULT := "default"

@export var blackboard: Dictionary = {}:
	set(b):
		blackboard = b.duplicate(true)
		_data[DEFAULT] = blackboard

var _data: Dictionary = {}


func _ready() -> void:
	blackboard = blackboard.duplicate(true)
	_data[DEFAULT] = blackboard


func keys() -> Array[String]:
	return _data.keys().duplicate()


func set_value(key: Variant, value: Variant, blackboard_name: String = DEFAULT) -> void:
	if not _data.has(blackboard_name):
		_data[blackboard_name] = {}
	_data[blackboard_name][key] = value


func get_value(key: Variant, default_value: Variant = null, blackboard_name: String = DEFAULT) -> Variant:
	if has_value(key, blackboard_name):
		return _data[blackboard_name].get(key, default_value)
	return default_value


func has_value(key: Variant, blackboard_name: String = DEFAULT) -> bool:
	return (
		_data.has(blackboard_name)
		and _data[blackboard_name].has(key)
		and _data[blackboard_name][key] != null
	)


func erase_value(key: Variant, blackboard_name: String = DEFAULT) -> void:
	if _data.has(blackboard_name):
		_data[blackboard_name][key] = null


func get_blackboard_names() -> Array[String]:
	return _data.keys().duplicate()


func get_blackboard(name: String = DEFAULT) -> Dictionary:
	return _data.get(name, {}).duplicate(true)
