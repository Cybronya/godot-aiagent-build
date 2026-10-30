extends SceneTree
## Phase 1.22 编排诊断事件验证（真实 Godot 运行时）。
##
## 覆盖：
##   T1 单阶段 Boss：orchestration_started / boss_death_confirmed / level_victory 各一次，
##      序号 +1、时间戳非递减、阶段字段 null 策略、重复死亡可观测且不重复结算。
##   T2 多阶段 Boss：stage_started/completed/transitioned 与阶段索引一致；清理未完成不推进；
##      Boss 死亡只完成一次；全事件契约字段与 JSON 安全性。
##   T3 玩家死亡：level_failed(player_died) 只一次；重复死亡通知被记录为忽略。
##   T4 运行期绑定失败：level_failed(setup_failed) 带可定位 field；重复 fail_setup 不重复终结。
##   T5 trace_enabled = false：零事件且游戏行为不变（仍 Completed）。
##   T6 显式路径导出 + JSON 读回 + 空路径 / 不存在目录失败返回 false，且不留文件。
##   T7 场景卸载后不再产生该运行的事件（trace 引用保留亦不变）。
##   T8 waves / holdout 回归：orchestration_started + 终结事件仍产生，且零 stage_* 事件。
##
## 用法：godot --headless --path . -s res://Tests/test_orchestration_trace.gd
## 全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。

const PLAYER_SCENE := "res://Features/player_movement/Player.tscn"
const BOSS_SCENE := "res://Scenes/Boss.tscn"
const ENEMY_SCENE := "res://Scenes/Enemy.tscn"
const TraceScript := preload("res://Orchestration/orchestration_trace.gd")

## Phase 1.33（F4-B）：本运行专属目录。临时配置与导出测试 trace 都落在
## `.ai/tmp/runs/<pid>-<16 位十六进制随机后缀，与 Python run_workspace 同一契约>/`，不再写共享的 `res://Levels` 与 `res://Tests`。
var _run_dir := _make_run_dir()
var TEMP_CONFIG := _run_dir + "/E2eOrchestrationTraceTest.json"
var EXPORT_PATH := _run_dir + "/e2e_trace_export_test.json"
var _owned: Dictionary = {}

const REQUIRED_FIELDS := ["schema_version", "run_id", "sequence", "event_type",
	"timestamp_ms", "stage_id", "stage_index", "source", "reason", "entity_id",
	"instance_name", "data"]

var _failures: PackedStringArray = []
var _finish_events: Array = []


func _initialize() -> void:
	_remove_temp()
	await _case_t1_single_stage()
	await _case_t2_multi_stage()
	await _case_t3_player_death()
	await _case_t4_setup_failure()
	await _case_t5_trace_disabled()
	await _case_t6_export_readback()
	await _case_t7_unload()
	await _case_t8_waves_holdout()
	_remove_temp()
	_report()


# ---------- T1：单阶段 Boss 事件契约 ----------


func _case_t1_single_stage() -> void:
	var host := _make_host()
	root.add_child(host["root"])
	await process_frame
	var orchestrator: LevelOrchestrator = host["orchestrator"]
	var config := LevelConfig.from_file(_write_boss_config("single", null))
	if not config.is_valid():
		_fail("T1: single-stage config rejected: %s" % str(config.errors))
		host["root"].queue_free()
		return
	orchestrator.finished.connect(func(success: bool) -> void: _finish_events.append(success))
	if not orchestrator.apply_config(config) \
			or not orchestrator.bind_boss("boss", host["boss"]):
		_fail("T1: setup failed: %s" % str(orchestrator.get_config_errors()))
		host["root"].queue_free()
		return
	orchestrator.start()
	await process_frame
	if orchestrator.trace.event_count() != 1:
		_fail("T1: start must record exactly one event, got %d"
			% orchestrator.trace.event_count())
		host["root"].queue_free()
		return
	var started: Dictionary = orchestrator.trace.events[0]
	if str(started.get("event_type", "")) != "orchestration_started":
		_fail("T1: first event must be orchestration_started, got %s"
			% str(started.get("event_type", "")))
	if started.get("stage_id") != null or started.get("stage_index") != null:
		_fail("T1: orchestration_started must not claim a stage")
	if str(_data_of(started).get("mode", "")) != "boss":
		_fail("T1: orchestration_started must carry mode=boss, got %s"
			% str(started.get("data")))
	var boss_health: Health = host["boss"].get_node("Health")
	boss_health.take_damage(9999)
	await process_frame
	_assert_trace_contract(orchestrator.trace, "T1")
	_assert_event_order(orchestrator.trace, "T1",
		["orchestration_started", "boss_death_confirmed", "level_victory"])
	var death := _first_event(orchestrator.trace, "boss_death_confirmed")
	if str(death.get("entity_id", "")) != "boss" \
			or str(death.get("instance_name", "")) != "Boss":
		_fail("T1: boss_death_confirmed must name the configured boss (got %s)"
			% str(death))
	if str(death.get("source", "")) != "boss_lifecycle":
		_fail("T1: boss_death_confirmed source must be boss_lifecycle")
	var victory := _first_event(orchestrator.trace, "level_victory")
	if str(victory.get("reason", "")) != "boss_defeated":
		_fail("T1: victory reason must be boss_defeated, got %s" % str(victory.get("reason")))
	if _finish_events != [true]:
		_fail("T1: finished(true) exactly once, got %s" % str(_finish_events))
	boss_health.died.emit()
	boss_health.died.emit()
	await process_frame
	var ignored := _events_of_type(orchestrator.trace, "duplicate_event_ignored")
	if ignored.size() != 2 or str(ignored[0].get("reason", "")) != "boss_death" \
			or str(ignored[1].get("reason", "")) != "boss_death":
		_fail("T1: each duplicate boss death must be observable, win=%d ignored=%s"
			% [_events_of_type(orchestrator.trace, "level_victory").size(), str(ignored)])
	if _events_of_type(orchestrator.trace, "level_victory").size() != 1 \
			or orchestrator.get_boss_defeated_events() != 1:
		_fail("T1: duplicate death must not re-settle victory")
	_assert_trace_contract(orchestrator.trace, "T1b")
	_finish_events.clear()
	host["root"].queue_free()
	await process_frame


# ---------- T2：多阶段阶段事件与推进顺序 ----------


func _case_t2_multi_stage() -> void:
	var host := _make_host()
	root.add_child(host["root"])
	await process_frame
	var orchestrator: LevelOrchestrator = host["orchestrator"]
	var stages := [_clear_stage("clear_1", 2), _boss_stage()]
	var config := LevelConfig.from_file(_write_boss_config("multi", stages))
	if not config.is_valid():
		_fail("T2: multi-stage config rejected: %s" % str(config.errors))
		host["root"].queue_free()
		return
	orchestrator.finished.connect(func(success: bool) -> void: _finish_events.append(success))
	if not orchestrator.apply_config(config) \
			or not orchestrator.bind_boss("boss", host["boss"]):
		_fail("T2: setup failed: %s" % str(orchestrator.get_config_errors()))
		host["root"].queue_free()
		return
	orchestrator.start()
	await process_frame
	var started := _events_of_type(orchestrator.trace, "stage_started")
	if started.size() != 1 or int(started[0].get("stage_index", -1)) != 0 \
			or str(started[0].get("stage_id", "")) != "clear_1":
		_fail("T2: clear stage must start as index 0/clear_1 (%s)" % str(started))
	var enemies := _stage_enemies(orchestrator)
	if enemies.size() != 2:
		_fail("T2: clear stage must spawn 2 enemies, got %d" % enemies.size())
		host["root"].queue_free()
		return
	enemies[0].get_node("Health").take_damage(9999)
	await process_frame
	if _events_of_type(orchestrator.trace, "stage_completed").size() != 0 \
			or orchestrator.get_stage_index() != 0:
		_fail("T2: partial clear must not complete the stage nor record stage_completed")
	enemies[1].get_node("Health").take_damage(9999)
	await process_frame
	_assert_trace_contract(orchestrator.trace, "T2a")
	var completed := _events_of_type(orchestrator.trace, "stage_completed")
	if completed.size() != 1 or int(completed[0].get("stage_index", -1)) != 0:
		_fail("T2: clear stage must complete exactly once (%s)" % str(completed))
	var transitions := _events_of_type(orchestrator.trace, "stage_transitioned")
	if transitions.size() != 1:
		_fail("T2: expected exactly one transition so far, got %d" % transitions.size())
	else:
		var data := _data_of(transitions[0])
		if int(data.get("from_stage_index", -1)) != 0 \
				or int(data.get("to_stage_index", -1)) != 1 \
				or str(data.get("to_stage_id", "")) != "boss" \
				or int(transitions[0].get("stage_index", -1)) != 1:
			_fail("T2: transition must record from 0 to 1 and carry the destination stage (%s)"
				% str(transitions[0]))
	var boss_stage := _events_of_type(orchestrator.trace, "stage_started")
	if boss_stage.size() != 2 \
			or str(boss_stage[1].get("reason", "")) != "defeat_boss" \
			or int(boss_stage[1].get("stage_index", -1)) != 1:
		_fail("T2: boss stage must start once at index 1 (%s)" % str(boss_stage))
	var boss_health: Health = host["boss"].get_node("Health")
	boss_health.take_damage(9999)
	await process_frame
	_assert_trace_contract(orchestrator.trace, "T2b")
	_assert_event_order(orchestrator.trace, "T2",
		["orchestration_started", "stage_started", "stage_completed", "stage_transitioned",
			"stage_started", "boss_death_confirmed", "stage_completed", "stage_transitioned",
			"level_victory"])
	var final_transition: Dictionary = _events_of_type(orchestrator.trace, "stage_transitioned")[1]
	var final_data := _data_of(final_transition)
	if final_data.get("to_stage_id") != null or final_transition.get("stage_id") != null \
			or str(final_transition.get("reason", "")) != "stages_exhausted":
		_fail("T2: exhausted stage chain must transition to null (%s)" % str(final_transition))
	if orchestrator.get_stage_history() != ["clear_1", "boss"] \
			or not orchestrator.are_stages_done():
		_fail("T2: runtime stage history must stay [clear_1, boss]")
	var summary: Dictionary = orchestrator.get_trace_summary()
	if int(summary.get("level_victory", 0)) != 1 \
			or int(summary.get("stage_started", 0)) != 2 \
			or int(summary.get("stage_completed", 0)) != 2:
		_fail("T2: event summary mismatch: %s" % str(summary))
	_finish_events.clear()
	host["root"].queue_free()
	await process_frame


# ---------- T3：玩家死亡失败语义 ----------


func _case_t3_player_death() -> void:
	var host := _make_host()
	root.add_child(host["root"])
	await process_frame
	var orchestrator: LevelOrchestrator = host["orchestrator"]
	var stages := [_clear_stage("clear_1", 1), _boss_stage()]
	var config := LevelConfig.from_file(_write_boss_config("player_fail", stages))
	orchestrator.finished.connect(func(success: bool) -> void: _finish_events.append(success))
	if not config.is_valid() or not orchestrator.apply_config(config) \
			or not orchestrator.bind_boss("boss", host["boss"]):
		_fail("T3: setup failed")
		host["root"].queue_free()
		return
	orchestrator.start()
	await process_frame
	var player_health: Health = host["player"].get_node("Health")
	player_health.take_damage(9999)
	await process_frame
	var failed := _events_of_type(orchestrator.trace, "level_failed")
	if failed.size() != 1 or str(failed[0].get("reason", "")) != "player_died" \
			or int(failed[0].get("stage_index", -1)) != 0:
		_fail("T3: player death must record one level_failed(player_died) with stage 0 (%s)"
			% str(failed))
	if orchestrator.state != LevelOrchestrator.State.Failed or _finish_events != [false]:
		_fail("T3: player death must keep Failed + finished(false) once")
	player_health.died.emit()
	await process_frame
	var ignored := _events_of_type(orchestrator.trace, "duplicate_event_ignored")
	if ignored.size() != 1 or str(ignored[0].get("reason", "")) != "player_death":
		_fail("T3: duplicate player death must be observable (%s)" % str(ignored))
	_assert_trace_contract(orchestrator.trace, "T3")
	_finish_events.clear()
	host["root"].queue_free()
	await process_frame


# ---------- T4：运行期绑定失败 ----------


func _case_t4_setup_failure() -> void:
	var host := _make_host()
	root.add_child(host["root"])
	await process_frame
	var orchestrator: LevelOrchestrator = host["orchestrator"]
	var stages := [_clear_stage("clear_1", 1), _boss_stage()]
	var config := LevelConfig.from_file(_write_boss_config("setup_fail", stages))
	if not config.is_valid() or not orchestrator.apply_config(config):
		_fail("T4: config rejected")
		host["root"].queue_free()
		return
	orchestrator.start()                                    # 未绑定 Boss → bind 失败
	await process_frame
	var failed := _events_of_type(orchestrator.trace, "level_failed")
	if failed.size() != 1 or str(failed[0].get("reason", "")) != "setup_failed":
		_fail("T4: setup failure must record one level_failed(setup_failed) (%s)"
			% str(failed))
	elif str(_data_of(failed[0]).get("field", "")) != "boss.instance":
		_fail("T4: setup failure must carry a locatable field, got %s" % str(failed[0]))
	if orchestrator.state != LevelOrchestrator.State.Failed:
		_fail("T4: runtime setup failure must keep Failed")
	orchestrator.fail_setup("probe", "second failure")
	await process_frame
	if _events_of_type(orchestrator.trace, "level_failed").size() != 1:
		_fail("T4: repeated setup failure must not record a second level_failed")
	var ignored := _events_of_type(orchestrator.trace, "duplicate_event_ignored")
	if ignored.size() != 1 or str(ignored[0].get("reason", "")) != "already_finished":
		_fail("T4: repeated setup failure must be observable as ignored (%s)" % str(ignored))
	_assert_trace_contract(orchestrator.trace, "T4")
	host["root"].queue_free()
	await process_frame


# ---------- T5：诊断关闭不改变行为 ----------


func _case_t5_trace_disabled() -> void:
	var host := _make_host()
	root.add_child(host["root"])
	await process_frame
	var orchestrator: LevelOrchestrator = host["orchestrator"]
	orchestrator.trace_enabled = false
	var config := LevelConfig.from_file(_write_boss_config("disabled", null))
	orchestrator.finished.connect(func(success: bool) -> void: _finish_events.append(success))
	if not config.is_valid() or not orchestrator.apply_config(config) \
			or not orchestrator.bind_boss("boss", host["boss"]):
		_fail("T5: setup failed")
		host["root"].queue_free()
		return
	orchestrator.start()
	await process_frame
	host["boss"].get_node("Health").take_damage(9999)
	await process_frame
	if orchestrator.trace.event_count() != 0 \
			or int(orchestrator.get_trace_report().get("event_count", -1)) != 0:
		_fail("T5: disabled diagnostics must record zero events, got %d"
			% orchestrator.trace.event_count())
	if orchestrator.state != LevelOrchestrator.State.Completed or _finish_events != [true]:
		_fail("T5: gameplay outcome must be unchanged when diagnostics are disabled")
	_finish_events.clear()
	host["root"].queue_free()
	await process_frame


# ---------- T6：显式路径导出 + 读回 ----------


func _case_t6_export_readback() -> void:
	var host := _make_host()
	root.add_child(host["root"])
	await process_frame
	var orchestrator: LevelOrchestrator = host["orchestrator"]
	var config := LevelConfig.from_file(_write_boss_config("export", null))
	orchestrator.finished.connect(func(success: bool) -> void: _finish_events.append(success))
	if not config.is_valid() or not orchestrator.apply_config(config) \
			or not orchestrator.bind_boss("boss", host["boss"]):
		_fail("T6: setup failed")
		host["root"].queue_free()
		return
	orchestrator.start()
	await process_frame
	host["boss"].get_node("Health").take_damage(9999)
	await process_frame
	if not orchestrator.export_trace_json(EXPORT_PATH):
		_fail("T6: export_trace_json must succeed for an explicit writable path")
	elif not FileAccess.file_exists(EXPORT_PATH):
		_fail("T6: exported trace file is missing")
	else:
		_owned[EXPORT_PATH] = FileAccess.get_file_as_string(EXPORT_PATH).sha256_text()
		var parsed = JSON.parse_string(FileAccess.get_file_as_string(EXPORT_PATH))
		if not (parsed is Dictionary):
			_fail("T6: exported trace must be a JSON object")
		else:
			var document: Dictionary = parsed
			if str(document.get("document", "")) != "orchestration_trace" \
					or float(document.get("schema_version", 0)) != 1.0 \
					or str(document.get("run_id", "")) != orchestrator.trace.run_id \
					or float(document.get("event_count", -1)) \
						!= float(orchestrator.trace.event_count()) \
					or not (document.get("events") is Array) \
					or (document.get("events") as Array).size() \
						!= orchestrator.trace.event_count():
				_fail("T6: exported document contract mismatch: %s" % str(document))
			if not TraceScript.is_json_safe(document):
				_fail("T6: exported document must stay JSON-safe")
			var exported_events: Array = document.get("events") \
				if document.get("events") is Array else []
			if exported_events.is_empty() \
					or str(exported_events[0].get("event_type", "")) != "orchestration_started":
				_fail("T6: exported events must start with orchestration_started")
	if orchestrator.export_trace_json(""):
		_fail("T6: empty export path must fail")
	if orchestrator.export_trace_json("res://no_such_dir_phase122/trace.json"):
		_fail("T6: unwritable export path must fail without crashing")
	_delete_owned(EXPORT_PATH)
	if FileAccess.file_exists(EXPORT_PATH):
		_fail("T6: export test file must be removed after the check")
	_finish_events.clear()
	host["root"].queue_free()
	await process_frame


# ---------- T7：场景卸载后不再产生事件 ----------


func _case_t7_unload() -> void:
	var host := _make_host()
	root.add_child(host["root"])
	await process_frame
	var orchestrator: LevelOrchestrator = host["orchestrator"]
	var stages := [_clear_stage("clear_1", 1), _boss_stage()]
	var config := LevelConfig.from_file(_write_boss_config("unload", stages))
	orchestrator.finished.connect(func(success: bool) -> void: _finish_events.append(success))
	if not config.is_valid() or not orchestrator.apply_config(config) \
			or not orchestrator.bind_boss("boss", host["boss"]):
		_fail("T7: setup failed")
		host["root"].queue_free()
		return
	orchestrator.start()
	await process_frame
	for enemy in _stage_enemies(orchestrator):
		enemy.get_node("Health").take_damage(9999)
	await process_frame
	host["boss"].get_node("Health").take_damage(9999)
	await process_frame
	var trace_ref = orchestrator.trace
	var count := trace_ref.event_count()
	var summary: Dictionary = trace_ref.summary()
	_finish_events.clear()
	host["root"].queue_free()
	await process_frame
	await process_frame
	if not is_instance_valid(trace_ref):
		_fail("T7: retained trace reference must stay valid")
	elif trace_ref.event_count() != count or trace_ref.summary() != summary:
		_fail("T7: freed host must not append events to the finished run")
	if _finish_events.size() != 0:
		_fail("T7: freed host must not emit residual finish events")


# ---------- T8：waves / holdout 回归 ----------


func _case_t8_waves_holdout() -> void:
	# waves：orchestration_started + level_failed(forced)，零 stage / boss 事件
	var waves_host := _make_host(false)
	root.add_child(waves_host["root"])
	await process_frame
	var waves_orchestrator: LevelOrchestrator = waves_host["orchestrator"]
	var waves_config := LevelConfig.make_waves([{
		"entries": [{"scene": load(ENEMY_SCENE), "count": 1}],
		"duration": 30.0,
	}])
	if not waves_config.is_valid() or not waves_orchestrator.apply_config(waves_config):
		_fail("T8: waves config rejected: %s" % str(waves_config.errors))
	else:
		waves_orchestrator.start()
		await process_frame
		var started := _first_event(waves_orchestrator.trace, "orchestration_started")
		if str(_data_of(started).get("mode", "")) != "waves":
			_fail("T8: waves orchestration_started must carry mode=waves")
		for enemy in _stage_enemies(waves_orchestrator):
			enemy.get_node("Health").take_damage(9999)
		await process_frame
		waves_orchestrator.finish(false)
		await process_frame
		var failed := _events_of_type(waves_orchestrator.trace, "level_failed")
		if failed.size() != 1 or str(failed[0].get("reason", "")) != "forced":
			_fail("T8: forced finish must record level_failed(forced) (%s) all=%s"
				% [str(failed), str(waves_orchestrator.trace.events)])
		if not _events_of_type(waves_orchestrator.trace, "stage_started").is_empty() \
				or not _events_of_type(waves_orchestrator.trace, "boss_death_confirmed").is_empty():
			_fail("T8: waves mode must not emit stage / boss events")
		_assert_trace_contract(waves_orchestrator.trace, "T8-waves")
	waves_host["root"].queue_free()
	await process_frame
	# holdout：生存计时到点即 level_victory(survive_duration)，零 stage 事件
	var holdout_host := _make_host(false)
	root.add_child(holdout_host["root"])
	await process_frame
	var holdout_orchestrator: LevelOrchestrator = holdout_host["orchestrator"]
	var holdout_config := LevelConfig.new()
	holdout_config.mode = LevelConfig.MODE_HOLDOUT
	holdout_config.survival_duration = 0.0
	if not holdout_orchestrator.apply_config(holdout_config):
		_fail("T8: holdout memory config rejected")
	else:
		holdout_orchestrator.start()
		await process_frame
		await process_frame
		var victory := _events_of_type(holdout_orchestrator.trace, "level_victory")
		if victory.size() != 1 or str(victory[0].get("reason", "")) != "survive_duration":
			_fail("T8: holdout must record one level_victory(survive_duration) (%s)"
				% str(victory))
		var started := _first_event(holdout_orchestrator.trace, "orchestration_started")
		if str(_data_of(started).get("mode", "")) != "holdout":
			_fail("T8: holdout orchestration_started must carry mode=holdout")
		if not _events_of_type(holdout_orchestrator.trace, "stage_started").is_empty():
			_fail("T8: holdout must not emit stage events")
		_assert_trace_contract(holdout_orchestrator.trace, "T8-holdout")
	holdout_host["root"].queue_free()
	await process_frame


# ---------- 断言辅助 ----------


## 逐事件校验契约：字段齐全、schema 版本、run_id 一致、序号 +1、时间戳非递减、
## 阶段字段策略、data 为 Dictionary、整体 JSON 安全。
func _assert_trace_contract(trace, label: String) -> void:
	var previous_sequence := -1
	var previous_timestamp := -1
	var run_id := str(trace.run_id)
	if run_id.is_empty():
		_fail("%s: trace run_id must not be empty" % label)
	for index in trace.events.size():
		var event: Dictionary = trace.events[index]
		var where := "%s[%d]" % [label, index]
		for field in REQUIRED_FIELDS:
			if not event.has(field):
				_fail("%s: missing field %s" % [where, field])
		if int(event.get("schema_version", 0)) != 1:
			_fail("%s: schema_version must be 1" % where)
		if str(event.get("run_id", "")) != run_id:
			_fail("%s: run_id must match the trace" % where)
		if int(event.get("sequence", -1)) != previous_sequence + 1:
			_fail("%s: sequence must increase by exactly 1 (got %s after %d)"
				% [where, str(event.get("sequence")), previous_sequence])
		previous_sequence = int(event.get("sequence", -1))
		var timestamp := int(event.get("timestamp_ms", -1))
		if timestamp < previous_timestamp:
			_fail("%s: timestamp_ms must be non-decreasing" % where)
		previous_timestamp = timestamp
		if not (event.get("data") is Dictionary):
			_fail("%s: data must be a Dictionary" % where)
		var event_type := str(event.get("event_type", ""))
		match event_type:
			"stage_started", "stage_completed":
				if event.get("stage_id") == null or event.get("stage_index") == null:
					_fail("%s: %s must carry stage_id/stage_index" % [where, event_type])
			"orchestration_started":
				if event.get("stage_id") != null or event.get("stage_index") != null:
					_fail("%s: orchestration_started must not carry a stage" % where)
		if str(event.get("source", "")).is_empty() or str(event.get("reason", "")).is_empty():
			_fail("%s: source/reason must be stable non-empty codes" % where)
		if not TraceScript.is_json_safe(event):
			_fail("%s: event must stay JSON-safe" % where)


func _assert_event_order(trace, label: String, expected: Array) -> void:
	var types: Array = []
	for event in trace.events:
		types.append(str(event.get("event_type", "")))
	if types != expected:
		_fail("%s: event order mismatch expected=%s actual=%s"
			% [label, str(expected), str(types)])


## GDScript 的 `or` 返回 bool（非 Python 式回退），因此统一用显式取值。
func _data_of(event: Dictionary) -> Dictionary:
	var value = event.get("data", {})
	return value if value is Dictionary else {}


func _events_of_type(trace, event_type: String) -> Array:
	var result: Array = []
	for event in trace.events:
		if str(event.get("event_type", "")) == event_type:
			result.append(event)
	return result


func _first_event(trace, event_type: String) -> Dictionary:
	var found := _events_of_type(trace, event_type)
	return found[0] if not found.is_empty() else {}


func _stage_enemies(orchestrator: LevelOrchestrator) -> Array[Node]:
	var result: Array[Node] = []
	for child in orchestrator.entities.get_children():
		if child.is_in_group("enemies") and is_instance_valid(child) \
				and not child.is_queued_for_deletion():
			result.append(child)
	return result


# ---------- 宿主 / 配置辅助 ----------


func _make_host(with_boss: bool = true, with_player: bool = true) -> Dictionary:
	var host := Node2D.new()
	host.name = "OrchestrationTraceHost"
	var entities := Node2D.new()
	entities.name = "Entities"
	host.add_child(entities)
	var boss: CharacterBody2D = load(BOSS_SCENE).instantiate()
	boss.name = "Boss"
	boss.position = Vector2(300, 0)
	if with_boss:
		entities.add_child(boss)
	var player: CharacterBody2D = load(PLAYER_SCENE).instantiate()
	player.name = "Player"
	player.add_to_group("players")
	player.position = Vector2(-500, 0)
	if with_player:
		host.add_child(player)
	var orchestrator := LevelOrchestrator.new()
	orchestrator.name = "LevelOrchestrator"
	host.add_child(orchestrator)
	orchestrator.player = player if with_player else null
	orchestrator.entities = entities
	orchestrator.spawn_offset = func() -> Vector2: return Vector2.ZERO
	return {"root": host, "entities": entities, "boss": boss, "player": player,
		"orchestrator": orchestrator}


func _clear_stage(stage_id: String, count: int) -> Dictionary:
	return {"id": stage_id, "type": "clear_enemies",
		"entries": [{"entity": "grunt", "count": count}]}


func _boss_stage() -> Dictionary:
	return {"id": "boss", "type": "defeat_boss", "entity": "boss"}


func _write_boss_config(name: String, stages: Variant) -> String:
	var document := {
		"schema": {"id": "level_orchestration", "version": 2},
		"level": {"id": "trace_%s" % name, "arena_scene": "res://Scenes/BossChallenge.tscn"},
		"mode": "boss",
		"entities": {"boss": {"scene": BOSS_SCENE}, "grunt": {"scene": ENEMY_SCENE}},
		"boss": {"entity": "boss", "instance": "Boss", "spawn": "existing"},
		"exit": {"unlock_when": "never"},
		"victory": {"condition": "boss_defeated"},
	}
	if stages != null:
		document["stages"] = stages
	_store_config(document)
	return TEMP_CONFIG


func _make_run_dir() -> String:
	var base := "user://.test_runs/runs"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(base))
	for attempt in 16:
		var id := "%d-%08x%08x" % [OS.get_process_id(), randi(), randi()]
		var candidate := base + "/" + id
		if DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(candidate)):
			continue                       # 标识冲突：拒绝接管，重试下一个候选
		if DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(candidate)) == OK:
			return candidate
	return ""


func _store_config(document: Dictionary) -> void:
	if _run_dir.is_empty() \
			or DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(_run_dir)) != OK:
		_fail("config: 无法创建运行目录 %s" % _run_dir)
		return
	var text := JSON.stringify(document, "  ") + "\n"
	var file := FileAccess.open(TEMP_CONFIG, FileAccess.WRITE)
	if file == null:
		_fail("config: 无法写入临时配置 %s" % TEMP_CONFIG)
		return
	file.store_string(text)
	file.close()
	_owned[TEMP_CONFIG] = text.sha256_text()


## 只删「本运行写入且内容未变」的资源；所有权无法证明 ⇒ 拒绝并报告。
func _delete_owned(path: String) -> void:
	if not FileAccess.file_exists(path):
		return
	if not _owned.has(path):
		_fail("ownership: 拒绝删除无所有权记录的资源 %s" % path)
		return
	var current := FileAccess.get_file_as_string(path)
	if current.sha256_text() != _owned[path]:
		_fail("ownership: 内容与本运行写入不一致，拒绝删除 %s" % path)
		return
	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	if FileAccess.file_exists(path):
		_fail("cleanup: 无法删除 %s" % path)


func _remove_temp() -> void:
	_delete_owned(TEMP_CONFIG)
	_delete_owned(EXPORT_PATH)
	if not _run_dir.is_empty() and DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(_run_dir)):
		if DirAccess.remove_absolute(ProjectSettings.globalize_path(_run_dir)) != OK:
			_fail("cleanup: 运行目录非空或无法删除 %s" % _run_dir)


func _fail(message: String) -> void:
	_failures.append(message)


## 只报告不删除：`res://Levels` / `res://Tests` 中前缀命中但**不属于本运行**的残留。
func _report_foreign_leftovers() -> void:
	for base: String in ["res://Levels", "res://Tests"]:
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
	if not _run_dir.is_empty() and DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(_run_dir)):
		_failures.append("T: 运行目录未清理 %s" % _run_dir)
	_report_foreign_leftovers()
	if _failures.is_empty():
		print("PASS: 编排诊断事件验证通过")
		quit(0)
		return
	for failure in _failures:
		printerr("FAIL: " + failure)
	quit(1)
