class_name ConditionGate
extends Node
## 条件聚合门：把 N 个布尔输入按 AND 聚合为单一输出状态。
##
## 纯逻辑组件：不知道输入来自开关、按钮还是脚本；各输入通过 set_condition(value, id)
## 上报，全部条件为 true 时输出翻转并广播。与 trigger_switch / openable_door 的
## 组合契约（同签名布尔信号/方法）直接对接，无需任何胶水脚本。
## 设计为「保持型」（All 模式）：条件达成后保持满足（与 Latching 开关语义一致）。
## 聚合契约：
## - All（默认）：fulfilled = 全部已上报条件为 true 且数量 ≥ condition_count
## - AtLeast：fulfilled = 当前值为 true 的条件数 ≥ condition_count（动态重评，
##   条件回落会立即使聚合回落；与 Toggle 源配合表达「至少 N 个激活」）
## 需要「条件失效则结果失效」的 All 模式动态重评，应扩展本组件而非另建。

signal fulfilled(is_fulfilled: bool)

enum Aggregation { All, AtLeast }

@export var condition_count := 2
@export var aggregation: Aggregation = Aggregation.All

var _states := {}
var _is_fulfilled := false


func is_fulfilled() -> bool:
	return _is_fulfilled


## 上报指定条件的状态；未声明的条件 id 首次上报时自动纳入聚合。
## value 在前、id 在后：场景连接用 binds 追加在信号参数之后，
## `activated(bool)` 直连时写法为 binds=["id"]，无需胶水脚本。
func set_condition(value: bool, id: String) -> void:
	_states[id] = value
	_evaluate()


## 将全部条件与输出恢复初始状态；由场景级重置流程调用。
func reset() -> void:
	_states.clear()
	_evaluate()


func _evaluate() -> void:
	var met: bool
	if aggregation == Aggregation.AtLeast:
		var true_count := 0
		for id: String in _states:
			if _states[id]:
				true_count += 1
		met = true_count >= condition_count
	else:
		met = true
		for id: String in _states:
			if not _states[id]:
				met = false
				break
		if condition_count > _states.size():
			met = false
	# 仅在跨越阈值时广播，重复上报同值不产生多余信号（幂等）
	if met != _is_fulfilled:
		_is_fulfilled = met
		fulfilled.emit(_is_fulfilled)
