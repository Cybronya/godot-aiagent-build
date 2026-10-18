class_name OrchestrationTrace
extends RefCounted
## 关卡编排诊断事件记录器（Phase 1.22）。
##
## 定位：**只观测生产状态机**，不替代、不驱动、不改写 `LevelOrchestrator` 的任何状态。
## 事件在真实状态变更边界由编排器写入；本类只负责契约字段、序号、相对时间与序列化。
##
## 契约（`.ai/context/orchestration_trace_schema.yaml`）：
##   - 每条事件都是可 JSON 序列化的纯数据（无 Godot 对象 / 指针 / Callable）；
##   - `sequence` 在单次 run_id 内从 0 起严格递增（+1，无重复、无倒退、无缺口）；
##   - `timestamp_ms` 是相对本次编排启动的单调时间（毫秒），非墙钟时间，允许相同；
##   - `schema_version` 必须显式为 1（回放器拒绝未知版本）；
##   - 阶段字段策略：阶段事件携带真实阶段身份；阶段外事件为 null；终结事件携带
##     最近一次活动阶段（若存在）。`data` 只放事件特有数据。
##
## 失败语义：记录器写入失败（导出失败 / 超过 MAX_EVENTS）不得影响编排结果；
## 溢出通过 `dropped_events` 如实计数，回放器据此判定 trace 不完整。

const DOCUMENT := "orchestration_trace"
const SCHEMA_VERSION := 1
## 单次运行的事件上限：防止诊断本身造成无界内存增长（溢出如实计数，不静默丢弃语义）
const MAX_EVENTS := 4096

var run_id := ""
var config_path := ""
var events: Array[Dictionary] = []
## 因超过 MAX_EVENTS 未能记录的事件数（>0 = trace 不完整）
var dropped_events := 0
var started := false

var _next_sequence := 0
var _start_ms := 0


## 开始一次运行：重置事件、序号与相对时间基准。同一实例重复 begin = 新运行。
func begin(run_id_value: String, start_ms: int, config_path_value: String = "") -> void:
	run_id = run_id_value
	config_path = config_path_value
	events.clear()
	dropped_events = 0
	_next_sequence = 0
	_start_ms = start_ms
	started = true


## 记录一条事件；返回写入的事件字典（未开始 / 溢出时返回空字典）。
## 参数不标类型：stage_id / stage_index / entity_id / instance_name 允许 null。
func record(event_type: String, source: String, reason: String,
		stage_id, stage_index, entity_id, instance_name, data: Dictionary = {}) -> Dictionary:
	if not started:
		return {}
	if events.size() >= MAX_EVENTS:
		dropped_events += 1
		return {}
	var event := {
		"schema_version": SCHEMA_VERSION,
		"run_id": run_id,
		"sequence": _next_sequence,
		"event_type": event_type,
		"timestamp_ms": Time.get_ticks_msec() - _start_ms,
		"stage_id": _nullable_string(stage_id),
		"stage_index": _nullable_int(stage_index),
		"source": source,
		"reason": reason,
		"entity_id": _nullable_string(entity_id),
		"instance_name": _nullable_string(instance_name),
		"data": data.duplicate(true),
	}
	_next_sequence += 1
	events.append(event)
	return event


func event_count() -> int:
	return events.size()


func is_empty() -> bool:
	return events.is_empty()


## 事件类型计数（稳定代码 → 次数）；供诊断与断言读取。
func summary() -> Dictionary:
	var counts := {}
	for event in events:
		var event_type := str(event.get("event_type", ""))
		counts[event_type] = int(counts.get(event_type, 0)) + 1
	return counts


## 完整 trace 文档（可 JSON 序列化）。
func to_dict() -> Dictionary:
	return {
		"document": DOCUMENT,
		"schema_version": SCHEMA_VERSION,
		"run_id": run_id,
		"config_path": config_path,
		"event_count": events.size(),
		"dropped_events": dropped_events,
		"events": events.duplicate(true),
	}


func to_json(pretty: bool = true) -> String:
	return JSON.stringify(to_dict(), "\t" if pretty else "")


## 显式路径导出（调用方必须给出明确位置；失败返回 false，绝不影响编排结果）。
func export_json(path: String) -> bool:
	if path.strip_edges().is_empty():
		return false
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return false
	file.store_string(to_json(true) + "\n")
	file.close()
	return true


## JSON 安全性（测试与导出前置检查）：只允许 null / bool / 数字 / 字符串 / 数组 / 字典。
static func is_json_safe(value) -> bool:
	if value == null:
		return true
	var type := typeof(value)
	if type == TYPE_BOOL or type == TYPE_INT or type == TYPE_FLOAT \
			or type == TYPE_STRING or type == TYPE_STRING_NAME:
		return true
	if type == TYPE_ARRAY:
		for item in value:
			if not is_json_safe(item):
				return false
		return true
	if type == TYPE_DICTIONARY:
		for key in value:
			if typeof(key) != TYPE_STRING and typeof(key) != TYPE_STRING_NAME:
				return false
			if not is_json_safe(value[key]):
				return false
		return true
	return false


static func _nullable_string(value):
	if value == null:
		return null
	if value is String or value is StringName:
		var text := str(value)
		return null if text.is_empty() else text
	return null


static func _nullable_int(value):
	if value == null or value is bool:
		return null
	if value is int:
		return value
	if value is float and float(value) == floor(float(value)):
		return int(value)
	return null
