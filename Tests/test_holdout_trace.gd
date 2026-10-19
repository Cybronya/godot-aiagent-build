extends SceneTree
## holdout 语义 trace 验证（Phase 1.27）：生成调度激活、正常完成、提前失败与终结后重复。
##
## 事件全部从生产导出接口 `SurvivalArena.export_trace_json` 读取（`OrchestrationTrace`
## 在真实状态变更边界写入），不手工拼装事件流。
##
## 覆盖（对应任务编号）：
##   H1 正常完成：orchestration_started(holdout) → spawn_schedule_started(0)
##      → level_victory(survive_duration)，且终结事件唯一并为最后一个
##   H2 无法满足条件的调度：delay 远大于 survival_duration 的调度不得产生事件
##      （不得虚构「调度已激活」）
##   H3 提前失败：生存期满前玩家死亡 → level_failed(player_died) 唯一且为最后一个事件，
##      且没有 level_victory
##   H4 终结后重复：胜利后再收到玩家死亡通知 → duplicate_event_ignored(player_death)，
##      终结事件仍然唯一（不产生第二个终结）
##   H5 未到期不结算：运行早期状态仍为 Playing，trace 中没有终结事件
##   H6 生产 trace 契约：序号 0 起 +1、时间戳非递减
##   H7 临时关卡配置与导出 trace 全部清理
##
## 用法：godot --headless --path . -s res://Tests/test_holdout_trace.gd

const ARENA_SCENE := "res://Scenes/SurvivalArena.tscn"
const ENEMY_SCENE := "res://Scenes/Enemy.tscn"
const WAIT_BUDGET := 900
## 生存时长：足够短以便在测试预算内完成，又足够长以让 0.3s 间隔的调度真正产出敌人
const DURATION := 0.8

## Phase 1.33（F4-B）：本运行专属目录。临时关卡配置与导出 trace 都落在
## `.ai/tmp/runs/<pid>-<16 位十六进制随机后缀，与 Python run_workspace 同一契约>/` 内（不再写共享的 `res://Levels` 与 `user://`），
## 目录名由本进程 pid + 微秒唯一确定；只有「本运行写入且内容未变」的资源才允许删除。
var _run_dir := _make_run_dir()
var TEMP_LEVEL := _run_dir + "/E2eHoldoutTraceTest.json"
var TRACE_PATH := _run_dir + "/e2e_holdout_trace_probe.json"
## path -> 本运行写入内容的 sha256（删除前必须匹配，否则拒绝删除）
var _owned: Dictionary = {}

var _failures: PackedStringArray = []
var _finish_events: Array = []
var _written: PackedStringArray = []
## 已完整跑完的用例数：GDScript 运行时错误会中断协程但不产生 FAIL —— 用该计数把
## 「用例被中断」变成失败，避免假通过。
var _cases_done := 0


func _make_run_dir() -> String:
	var base := "res://.ai/tmp/runs"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(base))
	for attempt in 16:
		var id := "%d-%08x%08x" % [OS.get_process_id(), randi(), randi()]
		var candidate := base + "/" + id
		if DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(candidate)):
			continue                       # 标识冲突：拒绝接管，重试下一个候选
		if DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(candidate)) == OK:
			return candidate
	return ""


func _initialize() -> void:
	await _case_holdout_semantic_chain()
	await _case_early_player_death()
	if _cases_done != 2:
		_fail("H0: 只完成了 %d/2 个用例（脚本运行时错误会中断协程）" % _cases_done)
	_cleanup()
	_report()


func _case_holdout_semantic_chain() -> void:
	var arena := await _fresh_arena()
	if arena == null:
		return
	var player: CharacterBody2D = arena.get_node("Player")

	# ---------------- H5: 未到期不结算 ----------------
	await physics_frame
	await physics_frame
	if arena.state != arena.State.Playing:
		_fail("H5: 生存期未满时应保持 Playing，实际 %d" % int(arena.state))
	if not _finish_events.is_empty():
		_fail("H5: 生存期未满时不得结算，实际 %s" % str(_finish_events))
	if _terminal_count(_trace_events(arena)) == 0:
		pass
	else:
		_fail("H5: 生存期未满时 trace 中不得出现终结事件")

	# ---------------- H1: 正常完成 ----------------
	if not await _wait_for_finish():
		_fail("H1: 生存时长到达后应结算（等待超时）")
	var events := _trace_events(arena)
	if arena.state != arena.State.Won:
		_fail("H1: 生存成功应进入 Won，实际 %d" % int(arena.state))
	if _finish_events != [true]:
		_fail("H1: 胜利事件应恰好一次 success=true，实际 %s" % str(_finish_events))

	var chain := _types(events)
	if chain == ["orchestration_started", "spawn_schedule_started", "level_victory"]:
		pass
	else:
		_fail("H1: 事件链应为 started → spawn_schedule_started(0) → victory，实际 %s" % str(chain))
	if str(events[0].get("reason", "")) != "holdout":
		_fail("H1: orchestration_started 的 reason 应为 holdout，实际 %s"
			% events[0].get("reason"))
	var schedule_event: Dictionary = events[1] if events.size() > 1 else {}
	var schedule_data: Dictionary = schedule_event.get("data", {})
	if int(schedule_data.get("schedule", -1)) != 0:
		_fail("H1: 首个激活的调度索引应为 0，实际 %s" % schedule_data)
	if str(schedule_data.get("entity", "")) != "enemy":
		_fail("H1: 调度事件应记录配置实体 id（enemy），实际 %s" % schedule_data)
	if absf(float(schedule_data.get("interval", 0.0)) - 0.3) > 0.0001:
		_fail("H1: 调度事件应记录配置 interval=0.3，实际 %s" % schedule_data)
	if str(events[-1].get("event_type", "")) != "level_victory" \
			or str(events[-1].get("reason", "")) != "survive_duration":
		_fail("H1: 最后一个事件应为 level_victory(survive_duration)，实际 %s/%s"
			% [events[-1].get("event_type"), events[-1].get("reason")])

	# ---------------- H2: 无法满足条件的调度不得产生事件 ----------------
	var activated := []
	for event in events:
		if str(event.get("event_type", "")) == "spawn_schedule_started":
			activated.append(int(event.get("data", {}).get("schedule", -1)))
	if activated == [0]:
		pass
	else:
		_fail("H2: 只有 delay 内的调度应激活（期望 [0]），实际 %s" % str(activated))

	# ---------------- H6: 生产 trace 契约 ----------------
	_check_contract(events, "H6")

	# ---------------- H4: 终结后重复通知不产生第二个终结 ----------------
	var health: Health = player.get_node("Health")
	if not health.is_dead():
		health.take_damage(9999)
	await physics_frame
	await physics_frame
	events = _trace_events(arena)
	if arena.state != arena.State.Won:
		_fail("H4: 胜利后再死亡不得改写终态，实际 %d" % int(arena.state))
	if _terminal_count(events) != 1:
		_fail("H4: 终结事件必须唯一，实际 %s" % str(_types(events)))
	if _has_event(events, "duplicate_event_ignored", "player_death"):
		pass
	else:
		_fail("H4: 终结后的玩家死亡应记 duplicate_event_ignored(player_death)，实际 %s"
			% str(_types(events)))
	if _count(events, "level_failed") == 0:
		pass
	else:
		_fail("H4: 胜利后不得出现 level_failed")
	_finish_events.clear()
	await _drop_arena(arena)
	_cases_done += 1


func _case_early_player_death() -> void:
	var arena := await _fresh_arena()
	if arena == null:
		return
	var player: CharacterBody2D = arena.get_node("Player")
	var health: Health = player.get_node("Health")
	health.take_damage(9999)
	await physics_frame
	await physics_frame
	if arena.state != arena.State.Lost:
		_fail("H3: 生存期满前死亡应进入 Lost，实际 %d" % int(arena.state))
	if _finish_events != [false]:
		_fail("H3: 失败事件应恰好一次 success=false，实际 %s" % str(_finish_events))
	var events := _trace_events(arena)
	if _terminal_count(events) != 1:
		_fail("H3: 失败路径必须恰好一个终结事件，实际 %s" % str(_types(events)))
	if str(events[-1].get("event_type", "")) != "level_failed" \
			or str(events[-1].get("reason", "")) != "player_died":
		_fail("H3: 最后一个事件应为 level_failed(player_died)，实际 %s/%s"
			% [events[-1].get("event_type"), events[-1].get("reason")])
	if _count(events, "level_victory") == 0:
		pass
	else:
		_fail("H3: 提前失败的 trace 中不得出现 level_victory")
	_check_contract(events, "H3b")
	_finish_events.clear()
	await _drop_arena(arena)
	_cases_done += 1


# ---------- 辅助 ----------


func _fresh_arena() -> Node2D:
	var config := {
		"schema": {"id": "level_orchestration", "version": 2},
		"level": {"id": "holdout_trace_test", "arena_scene": ARENA_SCENE},
		"mode": "holdout",
		"entities": {"enemy": {"scene": ENEMY_SCENE}},
		"holdout": {
			"survival_duration": DURATION,
			"max_alive": 4,
			"spawns": [
				{"entity": "enemy", "interval": 0.3},
				# 永远不会在生存期内到点：用于断言「未激活的调度不得产生事件」
				{"entity": "enemy", "delay": 30.0, "interval": 0.3},
			],
		},
		"victory": {"condition": "survive_duration"},
	}
	if not _write_json(TEMP_LEVEL, config):
		_fail("H0: 无法写入临时 holdout 配置 %s" % TEMP_LEVEL)
		return null
	var packed: PackedScene = load(ARENA_SCENE)
	if packed == null:
		_fail("H0: 无法加载 %s" % ARENA_SCENE)
		return null
	var arena: Node2D = packed.instantiate()
	arena.level_config_path = TEMP_LEVEL      # 必须在 _ready 之前设置
	arena.arena_finished.connect(_on_arena_finished)
	root.add_child(arena)
	await process_frame
	if not arena.get_config_errors().is_empty():
		_fail("H0: 临时 holdout 配置应被运行时接受，实际错误 %s" % str(arena.get_config_errors()))
	return arena


func _wait_for_finish() -> bool:
	for _i: int in WAIT_BUDGET:
		if not _finish_events.is_empty():
			return true
		await physics_frame
	return not _finish_events.is_empty()


func _drop_arena(arena: Node) -> void:
	arena.queue_free()
	await process_frame


func _trace_events(arena: Node) -> Array:
	if not arena.has_method("export_trace_json"):
		_fail("H0: 宿主场景应提供生产 trace 导出接口 export_trace_json")
		return []
	if not arena.export_trace_json(TRACE_PATH):
		_fail("H0: export_trace_json 应成功导出真实 trace")
		return []
	var file := FileAccess.open(TRACE_PATH, FileAccess.READ)
	if file == null:
		_fail("H0: 无法读取导出的 trace %s" % TRACE_PATH)
		return []
	var text := file.get_as_text()
	file.close()
	_owned[TRACE_PATH] = text.sha256_text()   # 导出后立即记录所有权摘要
	var document = JSON.parse_string(text)
	if typeof(document) != TYPE_DICTIONARY:
		_fail("H0: 导出的 trace 不是 JSON 对象")
		return []
	return document.get("events", [])


func _check_contract(events: Array, label: String) -> void:
	var contiguous := true
	var monotonic := true
	var previous := -1
	for index in events.size():
		var event: Dictionary = events[index]
		if int(event.get("sequence", -1)) != index:
			contiguous = false
		var timestamp := int(event.get("timestamp_ms", -1))
		if timestamp < previous:
			monotonic = false
		previous = maxi(previous, timestamp)
	if contiguous:
		pass
	else:
		_fail("%s: trace 事件序号应从 0 起严格 +1" % label)
	if monotonic:
		pass
	else:
		_fail("%s: trace 时间戳必须非递减" % label)


func _types(events: Array) -> Array:
	var result := []
	for event in events:
		result.append(str((event as Dictionary).get("event_type", "")))
	return result


func _count(events: Array, event_type: String) -> int:
	var total := 0
	for event in events:
		if str((event as Dictionary).get("event_type", "")) == event_type:
			total += 1
	return total


func _terminal_count(events: Array) -> int:
	return _count(events, "level_victory") + _count(events, "level_failed")


func _has_event(events: Array, event_type: String, reason: String = "") -> bool:
	for event in events:
		var item: Dictionary = event
		if str(item.get("event_type", "")) != event_type:
			continue
		if reason.is_empty() or str(item.get("reason", "")) == reason:
			return true
	return false


func _on_arena_finished(player_won: bool) -> void:
	_finish_events.append(player_won)


func _write_json(path: String, data: Dictionary) -> bool:
	if _run_dir.is_empty():
		return false
	if DirAccess.open(_run_dir) == null:
		if DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(_run_dir)) != OK:
			return false
	var text := JSON.stringify(data, "  ") + "\n"
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return false
	file.store_string(text)
	file.close()
	_owned[path] = text.sha256_text()
	_written.append(path)
	return true


func _cleanup() -> void:
	# 只删「本运行写入且内容未变」的资源；内容不符 = 所有权无法证明 ⇒拒绝并报告。
	for path: String in _owned.keys():
		if not FileAccess.file_exists(path):
			continue
		var current := FileAccess.get_file_as_string(path)
		if current.sha256_text() != _owned[path]:
			_fail("ownership: 内容与本运行写入不一致，拒绝删除 %s" % path)
			continue
		DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
		if FileAccess.file_exists(path):
			_fail("cleanup: 无法删除 %s" % path)
	if not _run_dir.is_empty() and DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(_run_dir)):
		if DirAccess.remove_absolute(ProjectSettings.globalize_path(_run_dir)) != OK:
			_fail("cleanup: 运行目录非空或无法删除 %s" % _run_dir)


func _fail(message: String) -> void:
	_failures.append(message)


## 只报告不删除：`res://Levels` / `user://` 中前缀命中但**不属于本运行**的残留。
## 无法证明所有权 ⇒ 拒绝删除（留给人工判断），不因残留而改变本测试的判定。
func _report_foreign_leftovers() -> void:
	for base: String in ["res://Levels", "user://"]:
		var dir := DirAccess.open(base)
		if dir == null:
			continue
		for file_name in dir.get_files():
			if not (file_name.begins_with("E2e") or file_name.begins_with("e2e_")):
				continue
			var path := base + "/" + file_name
			if not _owned.has(path):
				print("LEFTOVER (not owned by this run, not removed): %s" % path)


func _report() -> void:
	for path in _written:
		if FileAccess.file_exists(path):
			_failures.append("H7: 临时关卡配置未清理 %s" % path)
	if FileAccess.file_exists(TRACE_PATH):
		_failures.append("H7: 导出 trace 未清理 %s" % TRACE_PATH)
	if not _run_dir.is_empty() and DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(_run_dir)):
		_failures.append("H7: 运行目录未清理 %s" % _run_dir)
	_report_foreign_leftovers()
	if _failures.is_empty():
		print("PASS: holdout 语义 trace 验证通过（调度激活 → 正常完成 / 提前失败 / 终结后重复）")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
