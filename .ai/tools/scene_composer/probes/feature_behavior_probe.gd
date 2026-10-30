extends SceneTree
## Feature Behavior Probe（Phase 1.40 / 1.41 / 1.42）
##
## 在真实加载的场景里执行**协议声明的受限动作**，随后逐帧观测后置状态，写机器可读结果。
## 不做最终判定（判定归 feature_behavior_evidence.py），不伪造 PASS。
##
## Phase 1.41：能力定义不再硬编码在本文件——
##   协议 .ai/context/behavior_protocol.yaml（权威）
##     → 生成 probes/behavior_manifest.json（只读运行时清单）
##       → 本探针读取 manifest 校验契约
## 本文件只保留「实现 ID → 内部方法」的映射；未在 manifest 声明/未实现的能力一律拒绝。
##
## Phase 1.42（时间驱动能力；全部来自同一份 manifest）：
##   - simulation.advance_frames：真实推进 physics 帧（固定 delta），不使用私有回调；
##     process 帧不受节流、delta 非确定，因此未声明也不支持。
##   - state.set_property：只能写 manifest.properties 声明的属性，必须带 fixture 语义
##     且必须排在任何行为动作之前；记录 before / value / after。
##   - input.press / input.release：Input.action_press/release，动作名必须在 InputMap 中。
##   - node2d.position / node2d.displacement：读取真实 global_position；位移基线在动作前采集。
##   帧预算与夹具数量读自 manifest.limits，不在本文件另存常量。
##
## 用法：
##   godot --headless --path <project> -s res://.ai/tools/scene_composer/probes/feature_behavior_probe.gd \
##         -- --contract=<abs json> --result=<abs json>
##   godot --headless --path <project> -s ... -- --capabilities=<abs json>
##
## 契约（JSON，一次运行只含一个 behavior）：
##   feature / behavior / run_id / replay_index
##   scene             res:// 场景路径
##   window_frames     动作后观测窗口（physics frames）
##   actions[]         {type, target?, params?}
##   preconditions[]   {check, target, ...}
##   expected[]        同上（动作后的后置断言）
##
## 结果（JSON，同时以 BEHAVIOR_RESULT: 单行输出）：
##   status            PASS | MISMATCH | INSUFFICIENT | INVALID
##   reason            contract_invalid | protocol_invalid | action_unavailable |
##                     precondition_unmet | check_unavailable | state_mismatch |
##                     signal_mismatch | node_still_present | probe_error
##   action_executed   动作是否真的被调用（false 时调用方不得判 PASS）
##   actions[] / preconditions[] / checks[] / action_frame / observed_frame /
##   waited_frames / window_frames
##
## 约束：
##   - 只允许 manifest + 本文件 IMPLEMENTATION 映射中的能力；不执行任意方法名、
##     任意表达式或任意 GDScript。
##   - 只读场景：不写项目文件，只写 --result / --capabilities 指定的 JSON。
##   - 动作不可安全执行 / 观测不可用 / 协议缺失 → 非 PASS。

const RESULT_PREFIX := "BEHAVIOR_RESULT: "
const EXIT_INPUT := 2
const SETTLE_FRAMES := 2
const PROTOCOL_VERSION := 2
const MANIFEST_RES := "res://.ai/tools/scene_composer/probes/behavior_manifest.json"
const HEALTH_SCENE := "res://Features/health/Health.tscn"

## 实现 ID -> 本文件内部方法。协议只能引用这里存在的实现 ID。
const ACTION_IMPLEMENTATIONS := {
	"door_set_open": "_impl_door_set_open",
	"health_take_damage": "_impl_health_take_damage",
	"health_heal": "_impl_health_heal",
	"physics_overlap": "_impl_physics_overlap",
	"simulation_advance_frames": "_impl_simulation_advance_frames",
	"state_set_property": "_impl_state_set_property",
	"input_press": "_impl_input_press",
	"input_release": "_impl_input_release",
	"cooldown_start": "_impl_cooldown_start",
	"screenshake_add_trauma": "_impl_screenshake_add_trauma",
	"statemachine_start": "_impl_statemachine_start",
	"statemachine_transition_to": "_impl_statemachine_transition_to",
	"savegame_save_slot": "_impl_savegame_save_slot",
	"savegame_load_slot": "_impl_savegame_load_slot",
	"attackemitter_do_attack": "_impl_attackemitter_do_attack",
	"knockback_apply": "_impl_knockback_apply",
	"sfx_play": "_impl_sfx_play",
}

const OBSERVATION_IMPLEMENTATIONS := {
	"observe_door_is_open": "_observe_door_is_open",
	"observe_health_current": "_observe_health_current",
	"observe_health_is_dead": "_observe_health_is_dead",
	"observe_health_bar_ratio": "_observe_health_bar_ratio",
	"observe_pickup_is_collected": "_observe_pickup_is_collected",
	"observe_node_freed": "_observe_node_freed",
	"observe_node_exists": "_observe_node_exists",
	"observe_trigger_is_triggered": "_observe_trigger_is_triggered",
	"observe_gate_is_fulfilled": "_observe_gate_is_fulfilled",
	"observe_node2d_position": "_observe_node2d_position",
	"observe_node2d_displacement": "_observe_node2d_displacement",
	"observe_signal": "_observe_signal",
	"observe_cooldown_is_ready": "_observe_cooldown_is_ready",
	"observe_statemachine_current_state_name": "_observe_statemachine_current_state_name",
	"observe_savegame_last_slot": "_observe_savegame_last_slot",
	"observe_sfx_pool_active_count": "_observe_sfx_pool_active_count",
}

var _contract_path := ""
var _result_path := ""
var _capabilities_path := ""
var _manifest := {}
var _manifest_error := ""
var _scene: Node = null
var _actor: Node = null
var _signals := {}
var _signal_connects := {}
# Phase 1.52：target_path -> 连接期 watch_key。被监听目标可能在评估前被释放
# （如 projectile finished 后自释放），事件记录仍存活，评估需按连接期键读取。
var _watch_keys := {}
var _baselines := {}
var _pressed_actions: Array = []
# @actor 目标由 physics.overlap 在执行动作时才创建，因此这类信号监听先登记、
# 每次动作执行后再尝试连接（Phase 1.47；不增加任何新能力，只是补上既有
# `@actor` 目标在信号观测上的实现缺口）。
var _pending_actor_watches: Array = []
var _finished := false


func _initialize() -> void:
	_parse_args()
	if _capabilities_path != "":
		_write_capabilities()
		return
	if _contract_path == "" or _result_path == "":
		_finish({"status": "INVALID", "reason": "probe_error",
			"detail": "missing --contract/--result"}, EXIT_INPUT)
		return
	_manifest_error = _load_manifest()
	if _manifest_error != "":
		_finish({"status": "INVALID", "reason": "protocol_invalid",
			"detail": _manifest_error}, EXIT_INPUT)
		return
	var contract: Variant = _read_json(_contract_path)
	if typeof(contract) != TYPE_DICTIONARY or contract.is_empty():
		_finish({"status": "INVALID", "reason": "probe_error",
			"detail": "contract unreadable: " + _contract_path}, EXIT_INPUT)
		return
	await _run(contract)
	if not _finished:
		quit(0)


func _parse_args() -> void:
	for arg in OS.get_cmdline_user_args():
		var text := str(arg)
		if text.begins_with("--contract="):
			_contract_path = text.substr("--contract=".length())
		elif text.begins_with("--result="):
			_result_path = text.substr("--result=".length())
		elif text.begins_with("--capabilities="):
			_capabilities_path = text.substr("--capabilities=".length())


func _read_json(path: String) -> Variant:
	var handle := FileAccess.open(path, FileAccess.READ)
	if handle == null:
		return null
	var text := handle.get_as_text()
	handle.close()
	return JSON.parse_string(text)


func _write_json(path: String, payload: Dictionary) -> bool:
	var handle := FileAccess.open(path, FileAccess.WRITE)
	if handle == null:
		return false
	handle.store_string(JSON.stringify(payload))
	handle.close()
	return true


func _finish(payload: Dictionary, code: int = 0) -> void:
	_finished = true
	# 夹具必须可回滚：本次运行按下的输入一律释放，避免影响同进程内的其它读取。
	for name in _pressed_actions:
		Input.action_release(str(name))
	_pressed_actions.clear()
	var written := _write_json(_result_path, payload)
	if written:
		print(RESULT_PREFIX + JSON.stringify(payload))
	else:
		printerr("BEHAVIOR_PROBE_ERROR: cannot write result to " + _result_path)
	quit(code)


## 门禁探针：输出真实实现映射，供 Python 与协议对照（不读取契约）。
func _write_capabilities() -> void:
	var payload := {
		"protocol_version": PROTOCOL_VERSION,
		"actions": ACTION_IMPLEMENTATIONS.keys(),
		"observations": OBSERVATION_IMPLEMENTATIONS.keys(),
		"manifest_error": _load_manifest(),
	}
	_write_json(_capabilities_path, payload)
	quit(0)


func _load_manifest() -> String:
	var payload: Variant = _read_json(MANIFEST_RES)
	if typeof(payload) != TYPE_DICTIONARY:
		return "behavior manifest unreadable: " + MANIFEST_RES
	var data: Dictionary = payload
	var version := int(data.get("protocol_version", -1))
	if version != PROTOCOL_VERSION:
		return "incompatible behavior manifest version %d (probe expects %d)" % [
			version, PROTOCOL_VERSION]
	for key in ["actions", "observations", "signals"]:
		if typeof(data.get(key)) != TYPE_DICTIONARY:
			return "behavior manifest missing section: " + key
	_manifest = data
	return ""


func _run(contract: Dictionary) -> void:
	var scene_path := str(contract.get("scene", ""))
	var feature := str(contract.get("feature", ""))
	var behavior := str(contract.get("behavior", ""))
	var run_id := str(contract.get("run_id", ""))
	var window_frames := int(contract.get("window_frames", 0))
	var raw_actions: Array = contract.get("actions", [])
	var raw_preconditions: Array = contract.get("preconditions", [])
	var raw_expected: Array = contract.get("expected", [])
	var base := {"scene": scene_path, "feature": feature, "behavior": behavior,
		"run_id": run_id, "replay_index": int(contract.get("replay_index", 0))}

	if scene_path == "" or raw_actions.is_empty() or raw_expected.is_empty():
		_finish(_with(base, {"status": "INVALID", "reason": "contract_invalid",
			"detail": "contract requires scene, actions and expected"}))
		return
	var limits: Dictionary = _manifest.get("limits", {})
	var max_total_frames := int(limits.get("max_total_frames", 0))
	if window_frames < 0 or window_frames > max_total_frames:
		_finish(_with(base, {"status": "INVALID", "reason": "contract_invalid",
			"detail": "window_frames out of range"}))
		return

	var actions: Array = []
	for index in raw_actions.size():
		var validated := _validate_action(raw_actions[index], index)
		if not bool(validated.get("ok", false)):
			_finish(_with(base, {"status": "INVALID", "reason": "contract_invalid",
				"detail": str(validated.get("error", "")),
				"action_executed": false, "checks": []}))
			return
		actions.append(validated["action"])

	# 夹具顺序 / 夹具数量 / 帧预算：与 Python 校验共用 manifest.limits。
	var sequence := _check_action_sequence(actions)
	if not bool(sequence.get("ok", false)):
		_finish(_with(base, {"status": "INVALID", "reason": "contract_invalid",
			"detail": str(sequence.get("error", "")),
			"action_executed": false, "checks": []}))
		return
	var budget := _frame_budget(actions) + window_frames
	if budget > max_total_frames:
		_finish(_with(base, {"status": "INVALID", "reason": "contract_invalid",
			"detail": "frame budget %d exceeds max_total_frames %d" % [budget, max_total_frames],
			"action_executed": false, "checks": []}))
		return

	var preconditions: Array = []
	for index in raw_preconditions.size():
		var validated := _validate_check(raw_preconditions[index], index, "preconditions")
		if not bool(validated.get("ok", false)):
			_finish(_with(base, {"status": "INVALID", "reason": "contract_invalid",
				"detail": str(validated.get("error", "")),
				"action_executed": false, "checks": []}))
			return
		preconditions.append(validated["check"])

	var expected: Array = []
	for index in raw_expected.size():
		var validated := _validate_check(raw_expected[index], index, "expected")
		if not bool(validated.get("ok", false)):
			_finish(_with(base, {"status": "INVALID", "reason": "contract_invalid",
				"detail": str(validated.get("error", "")),
				"action_executed": false, "checks": []}))
			return
		expected.append(validated["check"])

	# 最小证据规则（Phase 1.45）：不推进任何 physics 帧、期望又只断言
	# 「什么都没发生」（signal count 0 / equals false）→ 契约非法，不得运行后
	# 在首个观测点就判 PASS（与 Python 契约校验同一份规则）。
	if _frame_budget(actions) == 0 and not _contract_has_evidence(expected):
		_finish(_with(base, {"status": "INVALID", "reason": "contract_invalid",
			"detail": "expected only asserts absence of behaviour while no action "
			+ "advances frames; no observation window",
			"action_executed": false, "checks": []}))
		return

	var packed: PackedScene = ResourceLoader.load(scene_path, "PackedScene",
		ResourceLoader.CACHE_MODE_IGNORE)
	if packed == null:
		_finish(_with(base, {"status": "MISMATCH", "reason": "load_error",
			"detail": "Failed to load scene: " + scene_path,
			"action_executed": false, "checks": []}))
		return
	_scene = packed.instantiate()
	if _scene == null:
		_finish(_with(base, {"status": "MISMATCH", "reason": "load_error",
			"detail": "Failed to instantiate scene: " + scene_path,
			"action_executed": false, "checks": []}))
		return
	root.add_child(_scene)
	for _i in SETTLE_FRAMES:
		await process_frame

	_connect_watches(preconditions)
	_connect_watches(expected)
	_capture_baselines(preconditions)
	_capture_baselines(expected)

	var precondition_checks := _evaluate(preconditions, 0, [])
	for check in precondition_checks:
		if str(check.get("status", "")) != "PASS":
			_finish(_with(base, {
				"status": "INSUFFICIENT", "reason": "precondition_unmet",
				"detail": "precondition not met: " + str(check.get("check", "")),
				"action_executed": false, "preconditions": precondition_checks,
				"checks": [], "actions": [],
			}))
			return

	var action_log: Array = []
	for action in actions:
		var record: Dictionary = await _execute(action)
		action_log.append(record)
		if bool(record.get("invalid", false)):
			_finish(_with(base, {"status": "INVALID", "reason": "contract_invalid",
				"detail": str(record.get("error", "invalid action")),
				"action_executed": false, "preconditions": precondition_checks,
				"checks": [], "actions": action_log,
			}))
			return
		if not bool(record.get("executed", false)):
			_finish(_with(base, {
				"status": "INSUFFICIENT", "reason": "action_unavailable",
				"detail": str(record.get("error", "action not executed")),
				"action_executed": false, "preconditions": precondition_checks,
				"checks": [], "actions": action_log,
			}))
			return
		# 动作可能刚创建了 @actor（physics.overlap）：现在才可能连接它的信号监听。
		_connect_actor_watches()

	var action_frame := Engine.get_process_frames()
	var checks := _evaluate(expected, 0, [])
	var waited := 0
	while waited < window_frames and not _all_pass(checks):
		await physics_frame
		waited += 1
		checks = _evaluate(expected, waited, checks)

	var status := "PASS"
	var reason := ""
	var detail := ""
	var unavailable := false
	for check in checks:
		var check_status := str(check.get("status", ""))
		if check_status == "PASS":
			continue
		if check_status == "UNAVAILABLE":
			unavailable = true
			continue
		if status == "PASS":
			status = "MISMATCH"
			reason = _reason_for(check)
			detail = "%s expected %s, observed %s" % [
				str(check.get("check", "")), str(check.get("expected")),
				str(check.get("observed"))]
	if unavailable:
		status = "INSUFFICIENT"
		reason = "check_unavailable"
		detail = "observation target/method unavailable"

	_finish(_with(base, {
		"status": status, "reason": reason, "detail": detail,
		"action_executed": true, "actions": action_log,
		"preconditions": precondition_checks, "checks": checks,
		"action_frame": action_frame,
		"observed_frame": Engine.get_process_frames(),
		"observed_physics_frame": Engine.get_physics_frames(),
		"waited_frames": waited,
		"window_frames": window_frames,
		"advanced_frames": _frame_budget(actions),
		"frame_budget": budget,
		"signals": _signal_counts(),
		"baselines": _baseline_snapshot(),
	}))


func _with(base: Dictionary, extra: Dictionary) -> Dictionary:
	var out := base.duplicate(true)
	for key in extra:
		out[key] = extra[key]
	return out


## 夹具（前置设置）必须在行为动作之前，且数量不得超限。
func _check_action_sequence(actions: Array) -> Dictionary:
	var limits: Dictionary = _manifest.get("limits", {})
	var max_fixtures := int(limits.get("max_fixture_actions", 0))
	var fixtures := 0
	var behaviors := 0
	var seen_behavior := false
	for index in actions.size():
		var spec: Dictionary = _manifest["actions"].get(str(actions[index].get("type", "")), {})
		if bool(spec.get("fixture", false)):
			fixtures += 1
			if seen_behavior:
				return {"ok": false, "error": "actions[%d] is a fixture action but follows " \
					% index + "a behavior action; setup must come first"}
		else:
			behaviors += 1
			seen_behavior = true
	if behaviors == 0:
		return {"ok": false, "error": "at least one non-fixture (behavior) action is required"}
	if fixtures > max_fixtures:
		return {"ok": false, "error": "%d fixture actions exceed the limit %d" \
			% [fixtures, max_fixtures]}
	return {"ok": true}


func _frame_budget(actions: Array) -> int:
	var total := 0
	for action in actions:
		var spec: Dictionary = _manifest["actions"].get(str(action.get("type", "")), {})
		if bool(spec.get("advances_frames", false)):
			total += int(action.get("params", {}).get("frames", 0))
	return total


## 期望集中是否包含可观测的正面证据：事件已发生（signal count > 0）、
## 布尔状态已到达（equals 为 true）或数值/区间断言。`count 0` / `equals false`
## 只断言「什么都没发生」，不构成证据。
func _contract_has_evidence(checks: Array) -> bool:
	for check in checks:
		var params: Dictionary = check.get("params", {})
		if str(check.get("check", "")) == "signal":
			if int(params.get("count", 0)) > 0:
				return true
			continue
		if not params.has("equals"):
			return true              # min/max 区间断言
		var value: Variant = params.get("equals")
		if typeof(value) != TYPE_BOOL:
			return true              # 数值/字符串断言（含 health.current == 0）
		if bool(value):
			return true              # equals: true
	return false


## 位移基线 = 动作前的真实位置；不根据预期值反推。
func _capture_baselines(entries: Array) -> void:
	for entry in entries:
		if str(entry.get("implementation", "")) != "observe_node2d_displacement":
			continue
		var target_path := str(entry.get("target", "."))
		if _baselines.has(target_path):
			continue
		var node := _resolve(target_path)
		if node is Node2D:
			_baselines[target_path] = (node as Node2D).global_position


func _baseline_snapshot() -> Dictionary:
	var out := {}
	for key in _baselines:
		var point: Vector2 = _baselines[key]
		out[key] = {"x": point.x, "y": point.y}
	return out


# ---------------------------------------------------------------- 契约校验

func _validate_action(raw: Variant, index: int) -> Dictionary:
	var where := "actions[%d]" % index
	if typeof(raw) != TYPE_DICTIONARY:
		return {"ok": false, "error": "%s must be a mapping" % where}
	var action: Dictionary = raw
	var action_type := str(action.get("type", ""))
	var spec: Dictionary = _manifest["actions"].get(action_type, {})
	if spec.is_empty():
		return {"ok": false, "error": "%s.type %s is not a registered action" % [where, action_type]}
	if not bool(spec.get("implemented", false)):
		return {"ok": false, "error": "%s.type %s is declared but not implemented" % [
			where, action_type]}
	var implementation := str(spec.get("implementation", ""))
	if not ACTION_IMPLEMENTATIONS.has(implementation):
		return {"ok": false, "error": "%s implementation %s is not available in this probe" % [
			where, implementation]}
	var p := _validate_params(spec.get("params", {}), action.get("params", {}), where)
	if not bool(p.get("ok", false)):
		return p
	var target_kind := str(spec.get("target", "node"))
	var target := str(action.get("target", "."))
	if not _valid_target(target):
		return {"ok": false, "error": "%s.target %s is not a scene path" % [where, target]}
	if target_kind == "none" and target != "" and target != ".":
		return {"ok": false, "error": "%s.target %s is not allowed for action %s " \
			% [where, target, action_type] + "(target kind none)"}
	var property_error := _check_property_refs(spec.get("params", {}), p["values"], where)
	if property_error != "":
		return {"ok": false, "error": property_error}
	return {"ok": true, "action": {"type": action_type, "target": target,
		"params": p["values"], "implementation": implementation,
		"fixture": bool(spec.get("fixture", false)),
		"advances_frames": bool(spec.get("advances_frames", false)),
		"target_kind": target_kind}}


## property_ref → 属性必须已在 manifest.properties 声明，且 value 落在 values 内。
func _check_property_refs(schema: Dictionary, params: Dictionary, where: String) -> String:
	for name in schema:
		if str(schema[name].get("type", "")) != "property_ref":
			continue
		var property_id := str(params.get(name, ""))
		var spec: Dictionary = _manifest.get("properties", {}).get(property_id, {})
		if spec.is_empty():
			return "%s.params.%s %s is not a registered property" % [where, name, property_id]
		var value: Variant = params.get("value")
		for allowed in spec.get("values", []):
			if _value_equal(allowed, value):
				return ""
		return "%s.params.value %s is not an allowed value for property %s" \
			% [where, value, property_id]
	return ""


func _validate_check(raw: Variant, index: int, where: String) -> Dictionary:
	var label := "%s[%d]" % [where, index]
	if typeof(raw) != TYPE_DICTIONARY:
		return {"ok": false, "error": "%s must be a mapping" % label}
	var entry: Dictionary = raw
	var check := str(entry.get("check", ""))
	var spec: Dictionary = _manifest["observations"].get(check, {})
	if spec.is_empty():
		return {"ok": false, "error": "%s.check %s is not a registered check" % [label, check]}
	if not bool(spec.get("implemented", false)):
		return {"ok": false, "error": "%s.check %s is declared but not implemented" % [
			label, check]}
	var implementation := str(spec.get("implementation", ""))
	if not OBSERVATION_IMPLEMENTATIONS.has(implementation):
		return {"ok": false, "error": "%s implementation %s is not available in this probe" % [
			label, implementation]}
	var values := {}
	for key in entry:
		if key != "check" and key != "target":
			values[key] = entry[key]
	var p := _validate_params(spec.get("params", {}), values, label)
	if not bool(p.get("ok", false)):
		return p
	var target := str(entry.get("target", "."))
	if not _valid_target(target):
		return {"ok": false, "error": "%s.target %s is not a scene path" % [label, target]}
	var params: Dictionary = p["values"]
	if params.has("entry"):
		var signal_id := str(params["entry"])
		var signal_spec: Dictionary = _manifest["signals"].get(signal_id, {})
		if signal_spec.is_empty():
			return {"ok": false, "error": "%s.params.entry %s is not a registered signal" % [
				label, signal_id]}
		if params.has("last_args"):
			var declared: Array = signal_spec.get("args", [])
			var args: Array = params["last_args"]
			if args.size() > declared.size():
				return {"ok": false, "error": "%s.params.last_args has too many arguments" % label}
			for position in args.size():
				if not _type_matches(str(declared[position]), args[position]):
					return {"ok": false, "error": "%s.params.last_args[%d] type mismatch" % [
						label, position]}
	else:
		var result_type := str(spec.get("result", {}).get("type", ""))
		if params.has("equals") and not _type_matches(result_type, params["equals"]):
			return {"ok": false, "error": "%s.params.equals does not match result type %s" % [
				label, result_type]}
		if params.has("tolerance") and not params.has("equals"):
			return {"ok": false, "error": "%s.params.tolerance requires equals" % label}
		if params.has("min") and params.has("max") \
				and float(params["min"]) > float(params["max"]):
			return {"ok": false, "error": "%s.params.min must be <= max" % label}
		if result_type == "float" and not params.has("equals") \
				and not params.has("min") and not params.has("max"):
			return {"ok": false, "error": "%s declares neither equals nor min/max; " \
				% label + "a float observation must be decidable"}
	return {"ok": true, "check": {"check": check, "target": target,
		"params": params, "implementation": implementation,
		"target_kind": str(spec.get("target", "node"))}}


func _validate_params(schema: Dictionary, values: Variant, where: String) -> Dictionary:
	var provided := {}
	if typeof(values) == TYPE_DICTIONARY:
		provided = values
	elif values != null:
		return {"ok": false, "error": "%s.params must be a mapping" % where}
	for key in provided:
		if not schema.has(key):
			return {"ok": false, "error": "%s.params has unknown key %s" % [where, key]}
	var normalized := {}
	for name in schema:
		var spec: Dictionary = schema[name]
		if not provided.has(name):
			if bool(spec.get("required", false)):
				return {"ok": false, "error": "%s.params.%s is required" % [where, name]}
			if spec.has("default"):
				normalized[name] = spec["default"]
			continue
		var value: Variant = provided[name]
		if not _param_value_ok(value, spec):
			return {"ok": false, "error": "%s.params.%s does not match type %s" % [
				where, name, str(spec.get("type", ""))]}
		normalized[name] = value
	return {"ok": true, "values": normalized}


func _param_value_ok(value: Variant, spec: Dictionary) -> bool:
	var kind := str(spec.get("type", ""))
	if kind == "bool":
		return typeof(value) == TYPE_BOOL
	if kind == "int":
		if not _is_int(value):
			return false
		var number := int(value)
		return number >= int(spec.get("min", -2147483648)) \
			and number <= int(spec.get("max", 2147483647))
	if kind == "float":
		if typeof(value) != TYPE_FLOAT and typeof(value) != TYPE_INT:
			return false
		var real_number := float(value)
		return real_number >= float(spec.get("min", -2147483648.0)) \
			and real_number <= float(spec.get("max", 2147483648.0))
	if kind == "enum":
		for allowed in spec.get("values", []):
			if _value_equal(allowed, value):
				return true
		return false
	if kind == "any":
		return value != null
	if kind == "string":
		if typeof(value) != TYPE_STRING:
			return false
		return not bool(spec.get("non_empty", false)) or str(value).strip_edges() != ""
	if kind == "scalar_list":
		if typeof(value) != TYPE_ARRAY:
			return false
		for item in value:
			if not (typeof(item) == TYPE_BOOL or _is_int(item) or typeof(item) == TYPE_STRING):
				return false
		return true
	if kind == "signal_ref" or kind == "property_ref":
		return typeof(value) == TYPE_STRING and str(value) != ""
	return false


func _is_int(value: Variant) -> bool:
	if typeof(value) == TYPE_INT:
		return true
	if typeof(value) == TYPE_FLOAT:
		return is_equal_approx(float(value), round(float(value)))
	return false


func _type_matches(declared: String, value: Variant) -> bool:
	if declared == "bool":
		return typeof(value) == TYPE_BOOL
	if declared == "int":
		return _is_int(value)
	if declared == "float":
		return typeof(value) == TYPE_FLOAT or typeof(value) == TYPE_INT
	if declared == "string":
		return typeof(value) == TYPE_STRING
	return false


func _valid_target(target: String) -> bool:
	if target == "" or target == "." or target == "@actor":
		return true
	var text := target
	if text.begins_with("@actor/"):
		text = text.substr("@actor/".length())
	if text.contains("..") or text.begins_with("/") or text.contains("\\"):
		return false
	return text != ""


func _target_matches(kind: String, node: Node) -> bool:
	if node == null:
		return false
	if kind == "node2d":
		return node is Node2D
	return true


# ---------------------------------------------------------------- 动作执行

func _execute(action: Dictionary) -> Dictionary:
	var target_kind := str(action.get("target_kind", "node"))
	var target_path := str(action.get("target", "."))
	var params: Dictionary = action.get("params", {})
	var record := {"type": str(action.get("type", "")), "target": target_path,
		"params": params, "executed": false, "error": "",
		"fixture": bool(action.get("fixture", false))}
	var node: Node = null
	if target_kind != "none":
		node = _resolve(target_path)
		if not _target_matches(target_kind, node):
			record["error"] = "target does not satisfy target kind %s" % target_kind
			return record
	var implementation := str(action.get("implementation", ""))
	var method := str(ACTION_IMPLEMENTATIONS.get(implementation, ""))
	if method == "":
		record["error"] = "implementation not available: " + implementation
		return record
	record["started_frame"] = Engine.get_physics_frames()
	var result: Variant = await call(method, node, params, record)
	var out: Dictionary = record
	if typeof(result) == TYPE_DICTIONARY:
		out = result
	out["ended_frame"] = Engine.get_physics_frames()
	out["advanced_frames"] = int(out["ended_frame"]) - int(out.get("started_frame", 0))
	return out


func _impl_door_set_open(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not node.has_method("set_open"):
		record["error"] = "target cannot set_open"
		return record
	node.call("set_open", bool(params.get("value", false)))
	record["executed"] = true
	return record


func _impl_health_take_damage(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not node.has_method("take_damage"):
		record["error"] = "target cannot take_damage"
		return record
	node.call("take_damage", int(params.get("amount", 0)))
	record["executed"] = true
	return record


func _impl_health_heal(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not node.has_method("heal"):
		record["error"] = "target cannot heal"
		return record
	node.call("heal", int(params.get("amount", 0)))
	record["executed"] = true
	return record


## 受控帧推进：真实 physics 帧（固定 delta），不使用私有回调也不改写状态。
func _impl_simulation_advance_frames(_node: Node, params: Dictionary,
		record: Dictionary) -> Dictionary:
	var frames := int(params.get("frames", 0))
	var phase := str(params.get("phase", "physics"))
	if phase != "physics":
		record["error"] = "frame phase %s is not supported (only physics)" % phase
		record["invalid"] = true
		return record
	if frames < 1:
		record["error"] = "frames must be >= 1"
		record["invalid"] = true
		return record
	record["phase"] = phase
	for _i in frames:
		await physics_frame
	record["executed"] = true
	return record


## 受约束的状态设置（夹具）：仅 manifest.properties 声明的属性；
## 必须带 fixture 语义且排在行为动作之前（由 _check_action_sequence 保证）。
func _impl_state_set_property(node: Node, params: Dictionary,
		record: Dictionary) -> Dictionary:
	var property_id := str(params.get("property", ""))
	var spec: Dictionary = _manifest.get("properties", {}).get(property_id, {})
	if spec.is_empty():
		record["error"] = "property %s is not declared in the protocol" % property_id
		record["invalid"] = true
		return record
	if node == null:
		record["error"] = "state.set_property target is unavailable"
		return record
	var expected_class := str(spec.get("class", ""))
	var actual_class := _script_global_name(node)
	if actual_class != expected_class:
		record["error"] = "target class %s does not match declared %s" % [
			actual_class, expected_class]
		return record
	var prop := str(spec.get("property", ""))
	if not _has_property(node, prop):
		record["error"] = "target has no property %s" % prop
		return record
	var value: Variant = params.get("value")
	var resolved: Variant = _enum_value_for(node, prop, str(value))
	if resolved == null:
		record["error"] = "property %s does not accept value %s (enum hint mismatch)" % [
			prop, str(value)]
		record["invalid"] = true
		return record
	record["before"] = node.get(prop)
	node.set(prop, resolved)
	record["property"] = property_id
	record["value"] = value
	record["after"] = node.get(prop)
	record["fixture"] = true
	record["executed"] = true
	return record


func _script_global_name(node: Node) -> String:
	var script: Variant = node.get_script()
	if script == null:
		return ""
	if script.has_method("get_global_name"):
		return str(script.get_global_name())
	return ""


func _has_property(node: Node, name: String) -> bool:
	for entry in node.get_property_list():
		if str(entry.get("name", "")) == name:
			return true
	return false


## 按属性 hint_string 把枚举名解析成序号；hint 不含该名字 → null（拒绝）。
## Godot 4.7 的导出枚举 hint 形如 "Latching:0,Repeat:1,Toggle:2"（名字:值）；
## 旧式无序号形式 "A,B" 按出现顺序取下标。
func _enum_value_for(node: Node, name: String, label: String) -> Variant:
	for entry in node.get_property_list():
		if str(entry.get("name", "")) != name:
			continue
		var hint := str(entry.get("hint_string", ""))
		if hint == "":
			return null
		var items := hint.split(",", false)
		for index in items.size():
			var item := str(items[index]).strip_edges()
			var label_part := item
			var value_text := str(index)
			if item.contains(":"):
				var bits := item.split(":", false, 1)
				var left := str(bits[0]).strip_edges()
				var right := str(bits[1]).strip_edges() if bits.size() > 1 else ""
				if right.is_valid_int():
					label_part = left
					value_text = right
				elif left.is_valid_int():
					label_part = right
					value_text = left
				else:
					label_part = left
					value_text = str(index)
			if label_part == label:
				return int(value_text)
		return null
	return null


func _impl_input_press(_node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	var action_name := str(params.get("action", ""))
	if not InputMap.has_action(action_name):
		record["error"] = "input action %s is not defined in InputMap" % action_name
		record["invalid"] = true
		return record
	Input.action_press(action_name)
	if not _pressed_actions.has(action_name):
		_pressed_actions.append(action_name)
	record["action"] = action_name
	record["executed"] = true
	return record


func _impl_input_release(_node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	var action_name := str(params.get("action", ""))
	if not InputMap.has_action(action_name):
		record["error"] = "input action %s is not defined in InputMap" % action_name
		record["invalid"] = true
		return record
	Input.action_release(action_name)
	_pressed_actions.erase(action_name)
	record["action"] = action_name
	record["executed"] = true
	return record


## Phase 1.52：Cooldown.start(duration)。重启语义（冷却中重打重计、再次广播 started）
## 由组件定义；探针只调用公开方法。duration<=0 组件自拒（返回 false 不算探针错误）。
func _impl_cooldown_start(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not node.has_method("start"):
		record["error"] = "target cannot start a cooldown"
		return record
	var ok_started: bool = node.call("start", float(params.get("duration", 0.0)))
	record["executed"] = true
	record["accepted"] = ok_started
	return record


## Phase 1.52：ScreenShake.add_trauma(amount)。叠加 / 钳制 / 相机缺失拒绝由组件定义。
func _impl_screenshake_add_trauma(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not node.has_method("add_trauma"):
		record["error"] = "target cannot add trauma"
		return record
	var accepted: bool = node.call("add_trauma", float(params.get("amount", 0.0)))
	record["executed"] = true
	record["accepted"] = accepted
	return record


## Phase 1.53：StateMachine.start(state)。目标必须是带 start() 的 StateMachine。
func _impl_statemachine_start(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not node.has_method("start"):
		record["error"] = "target is not a StateMachine"
		return record
	var state_name := str(params.get("state_name", ""))
	var state := node.get_node_or_null(state_name)
	if state == null:
		record["error"] = "no such StateNode child: " + state_name
		return record
	node.call("start", state)
	record["executed"] = true
	record["accepted"] = true
	return record


## Phase 1.53：StateMachine.transition_to(name)。
func _impl_statemachine_transition_to(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not node.has_method("transition_to"):
		record["error"] = "target is not a StateMachine"
		return record
	node.call("transition_to", str(params.get("state_name", "")))
	record["executed"] = true
	record["accepted"] = true
	return record


## Phase 1.53：SaveGame.save_to_slot(slot)。非法槽位名组件自拒（accepted=false）。
func _impl_savegame_save_slot(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not node.has_method("save_to_slot"):
		record["error"] = "target is not a SaveGame"
		return record
	var accepted: bool = node.call("save_to_slot", str(params.get("slot", "")))
	record["executed"] = true
	record["accepted"] = accepted
	return record


## Phase 1.53：SaveGame.load_from_slot(slot)。槽位不存在时组件返回 false。
func _impl_savegame_load_slot(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not node.has_method("load_from_slot"):
		record["error"] = "target is not a SaveGame"
		return record
	var accepted: bool = node.call("load_from_slot", str(params.get("slot", "")))
	record["executed"] = true
	record["accepted"] = accepted
	return record


## Phase 1.53：AttackEmitter.do_attack()。命中与结算由组件与物理决定。
func _impl_attackemitter_do_attack(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not node.has_method("do_attack"):
		record["error"] = "target is not an AttackEmitter"
		return record
	node.call("do_attack")
	record["executed"] = true
	record["accepted"] = true
	return record


## Phase 1.54：Knockback.apply(direction, force)。方向归一化、重启覆盖与无效拒绝
## （force<=0 / 零方向 / 宿主缺失）由组件定义；探针只调用公开方法。
func _impl_knockback_apply(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not node.has_method("apply"):
		record["error"] = "target cannot apply knockback"
		return record
	var direction := Vector2(float(params.get("dir_x", 0.0)), float(params.get("dir_y", 0.0)))
	var accepted: bool = node.call("apply", direction, float(params.get("force", 0.0)))
	record["executed"] = true
	record["accepted"] = accepted
	return record


## Phase 1.54：SfxPool.play(stream)。播放载荷由探针内部构造（短静音
## AudioStreamWAV）——协议参数是标量，无法表达流对象；轮转/抢占语义由组件定义。
func _impl_sfx_play(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not node.has_method("play"):
		record["error"] = "target cannot play sfx"
		return record
	var wav := AudioStreamWAV.new()
	# 1 秒静音（8bit/44100Hz = 44100 字节）：空数据流可能在音频 mix 线程调度下
	# 瞬间触发 finished，占用簿记变竞态（replay_inconsistent）；1s >> 观测窗口，
	# 播放在窗口内必然未结束，簿记确定。
	wav.data = PackedByteArray()
	wav.data.resize(44100)
	wav.format = AudioStreamWAV.FORMAT_8_BITS
	wav.mix_rate = 44100
	var accepted: bool = node.call("play", wav)
	record["executed"] = true
	record["accepted"] = accepted
	return record


## 受控物理接触：在目标位置生成真实 CharacterBody2D（可带真实 Health 实例），
## 由后续物理帧触发 Area2D.body_entered；不直接调用拾取物的私有回调。
func _impl_physics_overlap(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not (node is Node2D):
		record["error"] = "physics.overlap target is not a Node2D in the tree"
		return record
	var group := str(params.get("group", ""))
	if group == "":
		record["error"] = "physics.overlap requires params.group"
		return record

	var body := CharacterBody2D.new()
	body.name = "BehaviorActor"
	body.motion_mode = 1
	body.add_to_group(group)

	var health_max := int(params.get("health_max", 0))
	var damage := int(params.get("damage", 0))
	if health_max > 0 or damage > 0:
		var health_scene: PackedScene = ResourceLoader.load(HEALTH_SCENE, "PackedScene",
			ResourceLoader.CACHE_MODE_IGNORE)
		if health_scene == null:
			record["error"] = "Health.tscn unavailable for physics.overlap"
			return record
		var health: Node = health_scene.instantiate()
		health.name = "Health"
		health.set("max_health", max(health_max, 1))
		body.add_child(health)

	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(32, 32)
	shape.shape = rect
	body.add_child(shape)
	body.position = (node as Node2D).position
	root.add_child(body)
	_actor = body

	# Health._ready 已在入树时初始化；先扣血，再让物理帧触发接触。
	if damage > 0:
		var health_node := body.get_node_or_null("Health")
		if health_node == null or not health_node.has_method("take_damage"):
			record["error"] = "spawned Health cannot take_damage"
			return record
		health_node.call("take_damage", damage)
	record["executed"] = true
	return record


# ---------------------------------------------------------------- 观测

func _connect_watches(entries: Array) -> void:
	for entry in entries:
		if str(entry.get("implementation", "")) != "observe_signal":
			continue
		var target := str(entry.get("target", "."))
		if target == "@actor" or target.begins_with("@actor/"):
			# 目标尚不存在：登记后在每个动作执行结束时重试。
			_pending_actor_watches.append(entry)
			continue
		_connect_watch(entry)


## 动作执行后重试 @actor 监听：physics.overlap 每次生成新的实体，各自连一次。
func _connect_actor_watches() -> void:
	if _actor == null or not is_instance_valid(_actor):
		return
	for entry in _pending_actor_watches:
		_connect_watch(entry)


func _connect_watch(entry: Dictionary) -> void:
	var params: Dictionary = entry.get("params", {})
	var signal_id := str(params.get("entry", ""))
	var signal_spec: Dictionary = _manifest["signals"].get(signal_id, {})
	if signal_spec.is_empty():
		return
	var node := _resolve(str(entry.get("target", ".")))
	if node == null:
		return
	var signal_name := str(signal_spec.get("signal", ""))
	var watch_key := str(node.get_instance_id()) + "|" + signal_name
	if _signal_connects.has(watch_key):
		return
	if not node.has_signal(signal_name):
		return
	_signals[watch_key] = []
	var callback := func(a = null, b = null, c = null, d = null) -> void:
		_record_signal(watch_key, [a, b, c, d])
	node.connect(signal_name, callback)
	_signal_connects[watch_key] = true
	# 按 target+signal 组合登记（同一目标可监听多个信号，不能用 target 单键）。
	_watch_keys[str(entry.get("target", ".")) + "|" + signal_name] = watch_key


func _record_signal(watch_key: String, args: Array) -> void:
	if not _signals.has(watch_key):
		return
	var compact: Array = []
	for value in args:
		if value == null and compact.is_empty():
			continue
		compact.append(value)
	while not compact.is_empty() and compact[-1] == null:
		compact.pop_back()
	_signals[watch_key].append({"args": compact,
		"frame": Engine.get_process_frames()})


func _signal_counts() -> Dictionary:
	var out := {}
	for key in _signals:
		out[key] = _signals[key].size()
	return out


func _evaluate(entries: Array, frame: int, previous: Array) -> Array:
	var checks: Array = []
	var first_seen := {}
	for old in previous:
		if typeof(old) == TYPE_DICTIONARY and int(old.get("first_observed_frame", -1)) >= 0:
			first_seen[str(old.get("check", "")) + "|" + str(old.get("target", ""))] = \
				int(old.get("first_observed_frame"))
	for entry in entries:
		var params: Dictionary = entry.get("params", {})
		var target_path := str(entry.get("target", "."))
		var node := _resolve(target_path)
		var implementation := str(entry.get("implementation", ""))
		var method := str(OBSERVATION_IMPLEMENTATIONS.get(implementation, ""))
		var status := "PASS"
		var observed: Variant = null
		var expected_value: Variant = null
		# node.exists 的目标可能已消失：这是真实观测，不是“观测不可用”。
		# observe_signal 同理：目标可能在评估前被释放（自释放型组件），
		# 事件按连接期 watch_key 读取（见 _observe_signal）。
		var allows_missing := implementation == "observe_node_exists" \
			or implementation == "observe_signal"
		if method == "" or (node == null and not allows_missing):
			status = "UNAVAILABLE"
		elif node != null and not _target_matches(str(entry.get("target_kind", "node")), node):
			status = "UNAVAILABLE"
		else:
			var result: Dictionary = call(method, node, entry)
			if not bool(result.get("available", false)):
				status = "UNAVAILABLE"
			else:
				observed = result.get("observed")
				if implementation == "observe_signal":
					expected_value = int(params.get("count", 0))
					if int(observed) != int(expected_value):
						status = "SIGNAL_MISMATCH"
					elif params.has("last_args"):
						var events: Array = _signals.get(str(node.get_instance_id()) + "|"
							+ str(_manifest["signals"][params["entry"]]["signal"]), [])
						if events.is_empty() or not _args_equal(events[-1]["args"],
								params["last_args"]):
							status = "SIGNAL_MISMATCH"
				else:
					var verdict := _compare_observation(observed, params)
					expected_value = verdict["expected"]
					if not bool(verdict["pass"]):
						status = "STATE_MISMATCH"

		var seen := -1
		if status == "PASS":
			var cache_key := str(entry.get("check", "")) + "|" + target_path
			seen = int(first_seen.get(cache_key, frame))
		checks.append({
			"check": str(entry.get("check", "")),
			"target": target_path,
			"entry": str(params.get("entry", "")),
			"expected": expected_value,
			"observed": observed,
			"status": status,
			"first_observed_frame": seen,
		})
	return checks


func _observe_door_is_open(node: Node, _entry: Dictionary) -> Dictionary:
	if node == null or not node.has_method("is_open"):
		return {"available": false}
	return {"available": true, "observed": bool(node.call("is_open"))}


func _observe_health_current(node: Node, _entry: Dictionary) -> Dictionary:
	if node == null or not node.has_method("get_current_health"):
		return {"available": false}
	return {"available": true, "observed": int(node.call("get_current_health"))}


func _observe_health_is_dead(node: Node, _entry: Dictionary) -> Dictionary:
	if node == null or not node.has_method("is_dead"):
		return {"available": false}
	return {"available": true, "observed": bool(node.call("is_dead"))}


## Phase 1.52：Cooldown.is_ready() —— 节流判定的唯一公开读法。
func _observe_cooldown_is_ready(node: Node, _entry: Dictionary) -> Dictionary:
	if node == null or not node.has_method("is_ready"):
		return {"available": false}
	return {"available": true, "observed": bool(node.call("is_ready"))}


## Phase 1.53：StateMachine 当前状态名（未启动时为空串）。只读，不触发切换。
func _observe_statemachine_current_state_name(node: Node, _entry: Dictionary) -> Dictionary:
	if node == null or not ("current_state" in node):
		return {"available": false}
	var current = node.get("current_state")
	if current == null or not is_instance_valid(current):
		return {"available": true, "observed": ""}
	return {"available": true, "observed": String(current.name)}


## Phase 1.53：SaveGame 最近写入的槽位名。只读。
func _observe_savegame_last_slot(node: Node, _entry: Dictionary) -> Dictionary:
	if node == null or not node.has_method("get_last_slot"):
		return {"available": false}
	return {"available": true, "observed": String(node.call("get_last_slot"))}


## Phase 1.54：SfxPool 占用数。只读调用 active_count()——自管簿记，headless 下
## 与真实音频环境语义一致；没有该 getter 的节点 → UNAVAILABLE，不猜值。
func _observe_sfx_pool_active_count(node: Node, _entry: Dictionary) -> Dictionary:
	if node == null or not node.has_method("active_count"):
		return {"available": false}
	return {"available": true, "observed": int(node.call("active_count"))}


## Phase 1.50：血条实际用于绘制填充宽度的比例。只调用公开 getter，不写属性、不触发重绘。
## 没有该 getter 的节点（错类型 / 未挂组件）→ UNAVAILABLE，不猜值。
func _observe_health_bar_ratio(node: Node, _entry: Dictionary) -> Dictionary:
	if node == null or not node.has_method("get_ratio"):
		return {"available": false}
	return {"available": true, "observed": float(node.call("get_ratio"))}


func _observe_pickup_is_collected(node: Node, _entry: Dictionary) -> Dictionary:
	if node == null or not node.has_method("is_collected"):
		return {"available": false}
	return {"available": true, "observed": bool(node.call("is_collected"))}


func _observe_node_freed(node: Node, _entry: Dictionary) -> Dictionary:
	if node == null:
		return {"available": false}
	return {"available": true,
		"observed": not is_instance_valid(node) or node.is_queued_for_deletion()}


func _observe_node_exists(node: Node, _entry: Dictionary) -> Dictionary:
	return {"available": true,
		"observed": node != null and is_instance_valid(node) and not node.is_queued_for_deletion()}


func _observe_trigger_is_triggered(node: Node, _entry: Dictionary) -> Dictionary:
	if node == null or not node.has_method("is_triggered"):
		return {"available": false}
	return {"available": true, "observed": bool(node.call("is_triggered"))}


func _observe_gate_is_fulfilled(node: Node, _entry: Dictionary) -> Dictionary:
	if node == null or not node.has_method("is_fulfilled"):
		return {"available": false}
	return {"available": true, "observed": bool(node.call("is_fulfilled"))}


func _observe_node2d_position(node: Node, entry: Dictionary) -> Dictionary:
	if node == null or not (node is Node2D):
		return {"available": false}
	var params: Dictionary = entry.get("params", {})
	var point := (node as Node2D).global_position
	return {"available": true, "observed": point.x if str(params.get("axis", "x")) == "x" else point.y}


## 相对动作前基线的位移；基线缺失时不得用预期值反推。
func _observe_node2d_displacement(node: Node, entry: Dictionary) -> Dictionary:
	if node == null or not (node is Node2D):
		return {"available": false}
	var target_path := str(entry.get("target", "."))
	if not _baselines.has(target_path):
		return {"available": false}
	var params: Dictionary = entry.get("params", {})
	var base: Vector2 = _baselines[target_path]
	var delta := (node as Node2D).global_position - base
	return {"available": true, "observed": delta.x if str(params.get("axis", "x")) == "x" else delta.y}


func _observe_signal(node: Node, entry: Dictionary) -> Dictionary:
	var params: Dictionary = entry.get("params", {})
	var signal_id := str(params.get("entry", ""))
	var signal_spec: Dictionary = _manifest["signals"].get(signal_id, {})
	if signal_spec.is_empty():
		return {"available": false}
	var signal_name := str(signal_spec.get("signal", ""))
	# Phase 1.52：优先按连接期登记的 watch_key 读取——目标节点可能在评估前
	# 被释放（projectile finished 后自释放），此时 node 为 null 或已失效，
	# 但连接期建立的事件记录仍然存活，这是真实观测而不是“观测不可用”。
	var watch_key := str(_watch_keys.get(
		str(entry.get("target", ".")) + "|" + signal_name, ""))
	if watch_key == "":
		if node == null or not node.has_signal(signal_name):
			return {"available": false}
		watch_key = str(node.get_instance_id()) + "|" + signal_name
	if not _signals.has(watch_key):
		return {"available": false}
	return {"available": true, "observed": _signals[watch_key].size()}


func _resolve(target: String) -> Node:
	if target == "" or target == ".":
		return _scene
	if _scene == null or not is_instance_valid(_scene):
		return null
	if target.begins_with("@"):
		var parts := target.substr(1).split("/", false)
		if parts.is_empty() or parts[0] != "actor" or _actor == null:
			return null
		var node: Node = _actor
		for index in range(1, parts.size()):
			node = node.get_node_or_null(parts[index])
		return node
	return _scene.get_node_or_null(target)


func _value_equal(actual: Variant, expected: Variant, tolerance: float = 0.0) -> bool:
	if expected == null:
		return actual == null
	if typeof(expected) == TYPE_BOOL:
		return typeof(actual) == TYPE_BOOL and bool(actual) == bool(expected)
	if typeof(expected) == TYPE_FLOAT or typeof(expected) == TYPE_INT:
		if typeof(actual) != TYPE_FLOAT and typeof(actual) != TYPE_INT:
			return false
		return abs(float(actual) - float(expected)) <= maxf(tolerance, 0.0001)
	if typeof(expected) == TYPE_STRING:
		return str(actual) == str(expected)
	return actual == expected


## 观测判定：equals±tolerance 或 min/max 区间；都未声明的观测只记录不判定（Python 预先拒绝）。
func _compare_observation(observed: Variant, params: Dictionary) -> Dictionary:
	if params.has("equals"):
		var tolerance := float(params.get("tolerance", 0.0))
		return {"pass": _value_equal(observed, params["equals"], tolerance),
			"expected": params["equals"]}
	if params.has("min") or params.has("max"):
		var low: Variant = params.get("min")
		var high: Variant = params.get("max")
		var passed := true
		var value := float(observed)
		if low != null and value < float(low):
			passed = false
		if high != null and value > float(high):
			passed = false
		return {"pass": passed, "expected": {"min": low, "max": high}}
	return {"pass": true, "expected": null}


func _args_equal(actual: Array, expected: Array) -> bool:
	if actual.size() < expected.size():
		return false
	for index in expected.size():
		if not _value_equal(actual[index], expected[index]):
			return false
	return true


func _all_pass(checks: Array) -> bool:
	for check in checks:
		if str(check.get("status", "")) != "PASS":
			return false
	return true


func _reason_for(check: Dictionary) -> String:
	if str(check.get("check", "")) == "signal":
		return "signal_mismatch"
	if str(check.get("check", "")) == "node.freed":
		return "node_still_present"
	return "state_mismatch"
