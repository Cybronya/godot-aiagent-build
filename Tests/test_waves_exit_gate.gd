extends SceneTree
## waves 出口锁定语义验证（Phase 1.26）：出口未解锁时不得成立胜利。
##
## 与本文件相邻的编排测试不同，这里验证的是**终结边界的守卫**，并且直接从生产代码
## 导出的 trace 读取事件（`TimedCombatArena.export_trace_json` → `OrchestrationTrace`），
## 不手工拼装事件流。
##
## 覆盖（对应任务编号）：
##   G1 波次未清空时把玩家注入出口区（真实 Area2D body_entered 路径）→ 拒绝，
##      state 仍 Playing、无 level_victory、门仍关闭、trace 记 invalid_transition_rejected(exit_locked)
##   G2 清空第一波并再次注入（第二波未清空）→ 仍拒绝，door 仍关闭
##   G3 清空最后一波 → exit_unlocked 出现在最后一个 wave_cleared 之后，且尚未胜利
##   G4 真实输入走进出口区 → 胜利恰好一次，level_victory(exit_reached_after_unlock) 为最后事件
##   G5 生产 trace 契约：序号 0 起 +1、时间戳非递减、波次语义链完整
##   G6 临时关卡配置与导出 trace 全部清理
##   G7 宿主没有注入出口门（exit_door = null）时仍不得提前胜利——守卫不依赖门对象；
##      清空最后一波仍会记录 exit_unlocked，随后进入出口区才胜利
##
## 用法：godot --headless --path . -s res://Tests/test_waves_exit_gate.gd

const ARENA_SCENE := "res://Scenes/TimedCombatArena.tscn"
const ENEMY_SCENE := "res://Scenes/Enemy.tscn"
const MOVE_ACTION := "move_right"
const EXIT_START := Vector2(560, 0)
const ZONE_CENTER := Vector2(720, 0)
const OUTSIDE := Vector2(300, 0)
const EXIT_BUDGET := 300

## Phase 1.33（F4-B）：本运行专属目录。临时关卡配置与导出 trace 都落在
## `.ai/tmp/runs/<pid>-<16 位十六进制随机后缀，与 Python run_workspace 同一契约>/` 内（不再写共享的 `res://Levels` 与 `user://`）；
## 只有「本运行写入且内容未变」的资源才允许删除。
var _run_dir := _make_run_dir()
var TEMP_LEVEL := _run_dir + "/E2eWavesExitGateTest.json"
var TRACE_PATH := _run_dir + "/e2e_waves_exit_gate_trace.json"
var _owned: Dictionary = {}

var _failures: PackedStringArray = []
var _finish_events: Array = []
var _written: PackedStringArray = []


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
	await _case_exit_locked_blocks_victory()
	await _case_zone_without_door()
	_cleanup()
	_report()


func _case_exit_locked_blocks_victory() -> void:
	var config := {
		"schema": {"id": "level_orchestration", "version": 1},
		"level": {"id": "waves_exit_gate_test", "arena_scene": ARENA_SCENE},
		"entities": {"enemy": {"scene": ENEMY_SCENE}},
		"waves": [
			{"id": "wave_1", "duration": 30.0, "entries": [{"entity": "enemy", "count": 1}]},
			{"id": "wave_2", "duration": 30.0, "entries": [{"entity": "enemy", "count": 1}]},
		],
		"exit": {"unlock_when": "all_waves_cleared"},
		"victory": {"condition": "exit_reached_after_unlock"},
	}
	if not _write_json(TEMP_LEVEL, config):
		_fail("G0: 无法写入临时 waves 配置 %s" % TEMP_LEVEL)
		return
	var arena := await _load_arena(TEMP_LEVEL)
	if arena == null:
		return
	var door: StaticBody2D = arena.get_node("Mechanism/ExitDoor")
	var player: CharacterBody2D = arena.get_node("Player")

	# ---------------- G1: 出口锁定 + 波次未清空 → 注入出口区被拒绝 ----------------
	if door.is_open():
		_fail("G1: 初始状态下出口应关闭")
	player.global_position = OUTSIDE
	await _settle()
	player.global_position = ZONE_CENTER
	await _settle()
	if arena.state != arena.State.Playing:
		_fail("G1: 出口锁定时进入出口区不得结算（state=%d）" % int(arena.state))
	if not _finish_events.is_empty():
		_fail("G1: 出口锁定时不得发出结算事件，实际 %s" % str(_finish_events))
	if not door.is_open():
		pass
	else:
		_fail("G1: 未清空波次时出口不应被解锁")
	var events := _trace_events(arena)
	if events.is_empty():
		_fail("G1: 生产代码未导出任何 trace 事件")
	else:
		if not _count(events, "level_victory"):
			pass
		else:
			_fail("G1: 出口锁定时 trace 中不得出现 level_victory")
		if _has_event(events, "invalid_transition_rejected", "exit_locked"):
			pass
		else:
			_fail("G1: 被拒绝的提前胜利应记录 invalid_transition_rejected(exit_locked)，实际 %s"
				% str(_types(events)))

	# ---------------- G2: 第二波未清空时再次注入 → 仍拒绝 ----------------
	var first_wave := _live_enemies(arena)
	if first_wave.size() != 1:
		_fail("G2: 第一波应生成 1 个敌人，实际 %d" % first_wave.size())
		await _cleanup_arena(arena)
		return
	first_wave[0].get_node("Health").take_damage(9999)
	await _settle()
	if arena.wave_index != 1:
		_fail("G2: 清空第一波后应进入第二波（index=1），实际 %d" % arena.wave_index)
	if door.is_open():
		_fail("G2: 第二波未清空时出口不得解锁")
	player.global_position = OUTSIDE
	await _settle()
	player.global_position = ZONE_CENTER
	await _settle()
	if arena.state != arena.State.Playing:
		_fail("G2: 第二波未清空时进入出口区不得结算（state=%d）" % int(arena.state))
	events = _trace_events(arena)
	if _count(events, "level_victory") == 0:
		pass
	else:
		_fail("G2: 波次未清空时 trace 中不得出现 level_victory")
	if not _has_event(events, "exit_unlocked"):
		pass
	else:
		_fail("G2: 波次未清空时 trace 中不得出现 exit_unlocked")

	# ---------------- G3: 清空最后一波 → 解锁，但尚未胜利 ----------------
	var second_wave := _live_enemies(arena)
	if second_wave.size() != 1:
		_fail("G3: 第二波应生成 1 个敌人，实际 %d" % second_wave.size())
		await _cleanup_arena(arena)
		return
	second_wave[0].get_node("Health").take_damage(9999)
	await _settle()
	if not door.is_open():
		_fail("G3: 全部波次清空后出口应解锁")
	events = _trace_events(arena)
	var last_clear := _last_index(events, "wave_cleared")
	var unlock := _first_index(events, "exit_unlocked")
	if last_clear < 0 or unlock < 0:
		_fail("G3: 真实 trace 应同时含 wave_cleared 与 exit_unlocked，实际 %s" % str(_types(events)))
	elif unlock <= last_clear:
		_fail("G3: exit_unlocked 必须晚于最后一个 wave_cleared（clear=%d unlock=%d）"
			% [last_clear, unlock])
	if _count(events, "level_victory") == 0:
		pass
	else:
		_fail("G3: 仅解锁出口（玩家尚未进入出口区）时不得结算胜利")
	if arena.state != arena.State.Playing:
		_fail("G3: 解锁后、进入出口区前应仍为 Playing（state=%d）" % int(arena.state))

	# ---------------- G4: 真实输入走进出口区 → 胜利恰一次 ----------------
	player.global_position = EXIT_START
	await _settle()
	Input.action_press(MOVE_ACTION)
	for _i: int in EXIT_BUDGET:
		if arena.state == arena.State.Completed:
			break
		await physics_frame
	Input.action_release(MOVE_ACTION)
	if arena.state != arena.State.Completed:
		_fail("G4: 出口解锁后走进出口区应结算胜利（state=%d x=%.1f）"
			% [int(arena.state), player.global_position.x])
	if _finish_events != [true]:
		_fail("G4: 胜利事件应恰好发出一次且 success=true，实际 %s" % str(_finish_events))
	events = _trace_events(arena)
	var victories := _count(events, "level_victory")
	if victories == 1:
		pass
	else:
		_fail("G4: trace 中应恰好有 1 个 level_victory，实际 %d" % victories)
	var last_event: Dictionary = events[events.size() - 1] if not events.is_empty() else {}
	if str(last_event.get("event_type", "")) == "level_victory" \
			and str(last_event.get("reason", "")) == "exit_reached_after_unlock":
		pass
	else:
		_fail("G4: 最后一个事件应为 level_victory(exit_reached_after_unlock)，实际 %s/%s"
			% [last_event.get("event_type"), last_event.get("reason")])

	# ---------------- G5: 生产 trace 契约 ----------------
	var contiguous := true
	var monotonic := true
	var previous_timestamp := -1
	for index in events.size():
		var event: Dictionary = events[index]
		if int(event.get("sequence", -1)) != index:
			contiguous = false
		var timestamp := int(event.get("timestamp_ms", -1))
		if timestamp < previous_timestamp:
			monotonic = false
		previous_timestamp = maxi(previous_timestamp, timestamp)
	if contiguous:
		pass
	else:
		_fail("G5: trace 事件序号应从 0 起严格 +1，实际 %s"
			% str(events.map(func(event): return event.get("sequence"))))
	if monotonic:
		pass
	else:
		_fail("G5: trace 时间戳必须非递减")
	var expected_chain := ["started", "wave0", "clear0", "wave1", "clear1", "unlock"]
	var actual_chain := []
	for event in events:
		match str(event.get("event_type", "")):
			"orchestration_started":
				actual_chain.append("started")
			"wave_started":
				actual_chain.append("wave%d" % int(event.get("data", {}).get("wave", -1)))
			"wave_cleared":
				actual_chain.append("clear%d" % int(event.get("data", {}).get("wave", -1)))
			"exit_unlocked":
				actual_chain.append("unlock")
	if actual_chain == expected_chain:
		pass
	else:
		_fail("G5: 波次语义链应为 %s，实际 %s" % [str(expected_chain), str(actual_chain)])

	await _cleanup_arena(arena)


## G7：没有门的宿主（exit_door = null）——守卫仍必须成立
func _case_zone_without_door() -> void:
	_finish_events.clear()          # 上一个场景的合法胜利不应污染本场景的断言
	var arena := await _load_arena(TEMP_LEVEL)
	if arena == null:
		return
	var player: CharacterBody2D = arena.get_node("Player")
	# 模拟“宿主只提供出口区、没有注入门对象”的编排接入方式
	arena._orchestrator.exit_door = null

	player.global_position = OUTSIDE
	await _settle()
	player.global_position = ZONE_CENTER
	await _settle()
	if arena.state != arena.State.Playing:
		_fail("G7: 没有门对象时也不得提前胜利（state=%d）" % int(arena.state))
	if not _finish_events.is_empty():
		_fail("G7: 没有门对象时不得发出结算事件，实际 %s" % str(_finish_events))
	var events := _trace_events(arena)
	if _has_event(events, "invalid_transition_rejected", "exit_locked"):
		pass
	else:
		_fail("G7: 没有门对象时仍应记录 invalid_transition_rejected(exit_locked)，实际 %s"
			% str(_types(events)))

	# 逐波清空：最后一波清空后必须记录 exit_unlocked（解锁是编排语义，不依赖门）
	for _wave in 2:
		for enemy in _live_enemies(arena):
			enemy.get_node("Health").take_damage(9999)
		await _settle()
	events = _trace_events(arena)
	var unlock := _first_index(events, "exit_unlocked")
	var last_clear := _last_index(events, "wave_cleared")
	if unlock >= 0 and unlock > last_clear:
		pass
	else:
		_fail("G7: 没有门对象时也应在最后一波清空后记录 exit_unlocked（clear=%d unlock=%d）"
			% [last_clear, unlock])

	player.global_position = OUTSIDE
	await _settle()
	player.global_position = ZONE_CENTER
	await _settle()
	if arena.state != arena.State.Completed:
		_fail("G7: 全部波次清空后进入出口区应结算胜利（state=%d）" % int(arena.state))
	events = _trace_events(arena)
	if _count(events, "level_victory") == 1 \
			and _first_index(events, "exit_unlocked") < _first_index(events, "level_victory"):
		pass
	else:
		_fail("G7: 胜利应恰好一次且晚于 exit_unlocked，实际 %s" % str(_types(events)))
	_finish_events.clear()
	await _cleanup_arena(arena)


# ---------- 辅助 ----------


func _load_arena(level_path: String) -> Node2D:
	var packed: PackedScene = load(ARENA_SCENE)
	if packed == null:
		_fail("G0: 无法加载竞技场场景 %s" % ARENA_SCENE)
		return null
	var arena: Node2D = packed.instantiate()
	arena.level_config_path = level_path      # 必须在 _ready 之前设置
	arena.arena_finished.connect(_on_arena_finished)
	root.add_child(arena)
	await process_frame
	if not arena.get_config_errors().is_empty():
		_fail("G0: 临时配置应被运行时接受，实际错误 %s" % str(arena.get_config_errors()))
	return arena


## 等待物理与渲染帧：Area2D 的 body_entered / body_exited 需要物理帧才会触发
func _settle() -> void:
	for _i: int in 3:
		await physics_frame
	await process_frame


func _cleanup_arena(arena: Node) -> void:
	arena.queue_free()
	await process_frame


func _live_enemies(arena: Node) -> Array[Node]:
	var result: Array[Node] = []
	var entities := arena.get_node_or_null("Entities")
	if entities == null:
		return result
	for child in entities.get_children():
		if child.is_in_group("enemies") and is_instance_valid(child) \
				and not child.is_queued_for_deletion():
			result.append(child)
	return result


## 从生产导出接口读取本次运行的真实事件（不使用手工构造的事件）
func _trace_events(arena: Node) -> Array:
	if not arena.has_method("export_trace_json"):
		_fail("G0: 宿主场景应提供生产 trace 导出接口 export_trace_json")
		return []
	if not arena.export_trace_json(TRACE_PATH):
		_fail("G0: export_trace_json 应成功导出真实 trace")
		return []
	var file := FileAccess.open(TRACE_PATH, FileAccess.READ)
	if file == null:
		_fail("G0: 无法读取导出的 trace %s" % TRACE_PATH)
		return []
	var text := file.get_as_text()
	file.close()
	_owned[TRACE_PATH] = text.sha256_text()   # 导出后立即记录所有权摘要
	var document = JSON.parse_string(text)
	if typeof(document) != TYPE_DICTIONARY:
		_fail("G0: 导出的 trace 不是 JSON 对象")
		return []
	return document.get("events", [])


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


func _has_event(events: Array, event_type: String, reason: String = "") -> bool:
	for event in events:
		var item: Dictionary = event
		if str(item.get("event_type", "")) != event_type:
			continue
		if reason.is_empty() or str(item.get("reason", "")) == reason:
			return true
	return false


func _first_index(events: Array, event_type: String) -> int:
	for index in events.size():
		if str((events[index] as Dictionary).get("event_type", "")) == event_type:
			return index
	return -1


func _last_index(events: Array, event_type: String) -> int:
	var found := -1
	for index in events.size():
		if str((events[index] as Dictionary).get("event_type", "")) == event_type:
			found = index
	return found


func _on_arena_finished(success: bool) -> void:
	_finish_events.append(success)


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


## 只报告不删除：`res://Levels` / `user://` 中前缀命中但**不属于本运行**的残留。
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


func _fail(message: String) -> void:
	_failures.append(message)


func _report() -> void:
	for path in _written:
		if FileAccess.file_exists(path):
			_failures.append("G6: 临时关卡配置未清理 %s" % path)
	if FileAccess.file_exists(TRACE_PATH):
		_failures.append("G6: 导出 trace 未清理 %s" % TRACE_PATH)
	if not _run_dir.is_empty() and DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(_run_dir)):
		_failures.append("G6: 运行目录未清理 %s" % _run_dir)
	_report_foreign_leftovers()
	if _failures.is_empty():
		print("PASS: waves 出口锁定语义验证通过（锁定不胜利 → 解锁 → 胜利）")
		quit(0)
	else:
		for failure in _failures:
			printerr("FAIL: " + failure)
		quit(1)
