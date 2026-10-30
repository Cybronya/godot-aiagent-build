extends SceneTree
## Composite Behavior Probe（Phase 1.46）
##
## 在真实加载的**组合场景**里按阶段执行协议声明的受限动作，并在每个阶段观察中间状态，
## 写机器可读结果。不做最终判定（判定归 composite_behavior_evidence.py），不伪造 PASS。
##
## 能力来源（与单个 Feature 探针完全相同，不另存一份能力定义）：
##   .ai/context/behavior_protocol.yaml        → probes/behavior_manifest.json
##   .ai/context/composite_behavior_protocol.yaml → probes/composite_behavior_manifest.json
## 本文件只保留「实现 ID → 内部方法」的映射，并额外拒绝组合协议 denied_actions 中的动作。
##
## 与 Feature Behavior Probe 的差别（只有三点）：
##   1. 场景来自组合协议白名单（Scenes/ 下的正式场景），不在 Features/ 内；
##   2. 契约是**分阶段**的：每阶段有自己的动作、观测窗口与断言，按声明顺序执行；
##   3. 阶段失败立即停止，并记录 failed_stage / completed_stages —— 部分完成的链
##      绝不会被整条判 PASS。
##
## 用法：
##   godot --headless --path <project> -s res://.ai/tools/scene_composer/probes/composite_behavior_probe.gd \
##         -- --contract=<abs json> --result=<abs json>
##   godot --headless --path <project> -s ... -- --capabilities=<abs json>
##
## 契约（JSON，一次运行只含一个组合场景的一条链）：
##   scene_id / scene / run_id / replay_index
##   preconditions[]  场景加载后、第一阶段动作前必须成立
##   stages[]         {id, actions[], expected[], window_frames}
##
## 结果（JSON，同时以 COMPOSITE_RESULT: 单行输出）：
##   status           PASS | MISMATCH | INSUFFICIENT | INVALID
##   reason           contract_invalid | protocol_invalid | action_unavailable |
##                    precondition_unmet | check_unavailable | state_mismatch |
##                    signal_mismatch | stage_incomplete | probe_error
##   completed_stages / failed_stage / stages[] / checks[]
##
## 约束：
##   - 只允许 manifest + 本文件 IMPLEMENTATION 映射中的能力；不执行任意方法名、
##     任意表达式或任意 GDScript。
##   - 不写项目文件，只写 --result / --capabilities 指定的 JSON。
##   - 动作不可安全执行 / 观测不可用 / 协议缺失 → 非 PASS。

const RESULT_PREFIX := "COMPOSITE_RESULT: "
const EXIT_INPUT := 2
const SETTLE_FRAMES := 3
const BEHAVIOR_PROTOCOL_VERSION := 2
const COMPOSITE_MANIFEST_RES := \
	"res://.ai/tools/scene_composer/probes/composite_behavior_manifest.json"
const BEHAVIOR_MANIFEST_RES := \
	"res://.ai/tools/scene_composer/probes/behavior_manifest.json"
const HEALTH_SCENE := "res://Features/health/Health.tscn"

## 实现 ID -> 本文件内部方法。组合协议 denied_actions 中的动作在这里**故意缺失**：
## 组合证据必须来自真实组件交互，不能用夹具属性写入制造中间状态。
const ACTION_IMPLEMENTATIONS := {
	"door_set_open": "_impl_door_set_open",
	"health_take_damage": "_impl_health_take_damage",
	"health_heal": "_impl_health_heal",
	"physics_overlap": "_impl_physics_overlap",
	"simulation_advance_frames": "_impl_simulation_advance_frames",
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
var _composite := {}
var _denied: Array = []
var _manifest_error := ""
var _scene: Node = null
var _actors: Array = []
var _signals := {}
var _signal_connects := {}
var _baselines := {}
var _pressed_actions: Array = []
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
	_manifest_error = _load_manifests()
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
	# 夹具必须可回滚：本次运行按下的输入一律释放。
	for name in _pressed_actions:
		Input.action_release(str(name))
	_pressed_actions.clear()
	for actor in _actors:
		if is_instance_valid(actor):
			actor.queue_free()
	_actors.clear()
	var written := _write_json(_result_path, payload)
	if written:
		print(RESULT_PREFIX + JSON.stringify(payload))
	else:
		printerr("COMPOSITE_PROBE_ERROR: cannot write result to " + _result_path)
	quit(code)


## 门禁探针：输出真实实现映射，供 Python 与协议对照（不读取契约）。
func _write_capabilities() -> void:
	var payload := {
		"protocol_version": BEHAVIOR_PROTOCOL_VERSION,
		"actions": ACTION_IMPLEMENTATIONS.keys(),
		"observations": OBSERVATION_IMPLEMENTATIONS.keys(),
		"denied_actions": _denied,
		"manifest_error": _load_manifests(),
	}
	_write_json(_capabilities_path, payload)
	quit(0)


func _load_manifests() -> String:
	var behavior: Variant = _read_json(BEHAVIOR_MANIFEST_RES)
	if typeof(behavior) != TYPE_DICTIONARY:
		return "behavior manifest unreadable: " + BEHAVIOR_MANIFEST_RES
	var composite: Variant = _read_json(COMPOSITE_MANIFEST_RES)
	if typeof(composite) != TYPE_DICTIONARY:
		return "composite manifest unreadable: " + COMPOSITE_MANIFEST_RES
	var base: Dictionary = behavior
	var extra: Dictionary = composite
	if int(base.get("protocol_version", -1)) != BEHAVIOR_PROTOCOL_VERSION:
		return "incompatible behavior manifest version %d" % [
			int(base.get("protocol_version", -1))]
	if int(extra.get("extends_protocol_version", -1)) != BEHAVIOR_PROTOCOL_VERSION:
		return "composite manifest extends behavior protocol %d, probe expects %d" % [
			int(extra.get("extends_protocol_version", -1)), BEHAVIOR_PROTOCOL_VERSION]
	if typeof(extra.get("scenes")) != TYPE_DICTIONARY \
			or typeof(extra.get("limits")) != TYPE_DICTIONARY:
		return "composite manifest missing sections: scenes / limits"
	_manifest = base
	_composite = extra
	_denied = []
	for item in extra.get("denied_actions", []):
		if typeof(item) == TYPE_DICTIONARY:
			_denied.append(str(item.get("action", "")))
	return ""


func _run(contract: Dictionary) -> void:
	var scene_id := str(contract.get("scene_id", ""))
	var scene_path := str(contract.get("scene", ""))
	var run_id := str(contract.get("run_id", ""))
	var base := {"scene_id": scene_id, "scene": scene_path, "run_id": run_id,
		"replay_index": int(contract.get("replay_index", 0))}
	var limits: Dictionary = _composite.get("limits", {})
	var scenes: Dictionary = _composite.get("scenes", {})

	if scene_id == "" or not scenes.has(scene_id):
		_finish(_with(base, {"status": "INVALID", "reason": "contract_invalid",
			"detail": "scene_id %r is not in the composite protocol allowlist" % scene_id}))
		return
	var allowed := str(scenes[scene_id])
	if _normalize_res(scene_path) != allowed:
		_finish(_with(base, {"status": "INVALID", "reason": "contract_invalid",
			"detail": "scene %r is not the allowlisted path %r" % [scene_path, allowed]}))
		return

	var raw_stages: Variant = contract.get("stages", [])
	var min_stages := int(limits.get("min_stages", 2))
	var max_stages := int(limits.get("max_stages", 0))
	if typeof(raw_stages) != TYPE_ARRAY or raw_stages.size() < min_stages \
			or raw_stages.size() > max_stages:
		_finish(_with(base, {"status": "INVALID", "reason": "contract_invalid",
			"detail": "contract requires %d..%d stages" % [min_stages, max_stages]}))
		return

	var stages: Array = []
	var max_total := int(limits.get("max_total_frames", 0))
	var budget := 0
	for index in raw_stages.size():
		var validated := _validate_stage(raw_stages[index], index)
		if not bool(validated.get("ok", false)):
			_finish(_with(base, {"status": "INVALID", "reason": "contract_invalid",
				"detail": str(validated.get("error", "")),
				"action_executed": false, "checks": []}))
			return
		var stage: Dictionary = validated["stage"]
		budget += int(stage["frames"]) + int(stage["window_frames"])
		stages.append(stage)
	if budget > max_total:
		_finish(_with(base, {"status": "INVALID", "reason": "contract_invalid",
			"detail": "frame budget %d exceeds max_total_frames %d" % [budget, max_total],
			"action_executed": false, "checks": []}))
		return

	var raw_preconditions: Variant = contract.get("preconditions", [])
	if typeof(raw_preconditions) != TYPE_ARRAY:
		_finish(_with(base, {"status": "INVALID", "reason": "contract_invalid",
			"detail": "preconditions must be a list", "action_executed": false,
			"checks": []}))
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

	var packed: PackedScene = ResourceLoader.load(_normalize_res(scene_path), "PackedScene",
		ResourceLoader.CACHE_MODE_IGNORE)
	if packed == null:
		_finish(_with(base, {"status": "MISMATCH", "reason": "load_error",
			"detail": "Failed to load scene: " + scene_path,
			"action_executed": false, "checks": [], "completed_stages": []}))
		return
	_scene = packed.instantiate()
	if _scene == null:
		_finish(_with(base, {"status": "MISMATCH", "reason": "load_error",
			"detail": "Failed to instantiate scene: " + scene_path,
			"action_executed": false, "checks": [], "completed_stages": []}))
		return
	root.add_child(_scene)
	for _i in SETTLE_FRAMES:
		await process_frame

	# 信号监听必须在第一段动作之前全部建立：计数跨阶段累计，阶段边界即顺序证据。
	_connect_watches(preconditions)
	for stage in stages:
		_connect_watches(stage["expected"])

	var precondition_checks := _evaluate(preconditions, 0, [])
	for check in precondition_checks:
		if str(check.get("status", "")) != "PASS":
			_finish(_with(base, {
				"status": "INSUFFICIENT", "reason": "precondition_unmet",
				"detail": "precondition not met: " + str(check.get("check", "")),
				"action_executed": false, "preconditions": precondition_checks,
				"checks": [], "stages": [], "completed_stages": [], "failed_stage": null,
			}))
			return

	var stage_results: Array = []
	var completed: Array = []
	var all_checks: Array = []
	var action_executed := true
	var status := "PASS"
	var reason := ""
	var detail := ""
	var failed_stage: Variant = null

	for stage in stages:
		var stage_id := str(stage["id"])
		_baselines.clear()
		_capture_baselines(stage["expected"])
		var action_log: Array = []
		var stage_ok := true
		for action in stage["actions"]:
			var record: Dictionary = await _execute(action)
			action_log.append(record)
			if bool(record.get("invalid", false)):
				_finish(_with(base, {"status": "INVALID", "reason": "contract_invalid",
					"detail": str(record.get("error", "invalid action")),
					"action_executed": false, "checks": [],
					"stages": stage_results, "completed_stages": completed,
					"failed_stage": stage_id}))
				return
			if not bool(record.get("executed", false)):
				action_executed = false
				stage_ok = false
				status = "INSUFFICIENT"
				reason = "action_unavailable"
				detail = str(record.get("error", "action not executed"))
				break
		if not stage_ok:
			stage_results.append({"id": stage_id, "index": int(stage["index"]),
				"status": status, "reason": reason, "detail": detail,
				"actions": action_log, "checks": [], "waited_frames": null,
				"window_frames": int(stage["window_frames"])})
			failed_stage = stage_id
			break

		var action_frame := Engine.get_process_frames()
		var checks := _evaluate(stage["expected"], 0, [])
		var waited := 0
		while waited < int(stage["window_frames"]) and not _all_pass(checks):
			await physics_frame
			waited += 1
			checks = _evaluate(stage["expected"], waited, checks)

		var stage_status := "PASS"
		var stage_reason := ""
		var stage_detail := ""
		var unavailable := false
		for check in checks:
			var check_status := str(check.get("status", ""))
			if check_status == "PASS":
				continue
			if check_status == "UNAVAILABLE":
				unavailable = true
				continue
			if stage_status == "PASS":
				stage_status = "MISMATCH"
				stage_reason = _reason_for(check)
				stage_detail = "%s expected %s, observed %s" % [
					str(check.get("check", "")), str(check.get("expected")),
					str(check.get("observed"))]
		if unavailable and stage_status == "PASS":
			stage_status = "INSUFFICIENT"
			stage_reason = "check_unavailable"
			stage_detail = "observation target/method unavailable"
		elif unavailable:
			stage_status = "INSUFFICIENT"
			stage_reason = "check_unavailable"
			stage_detail = "observation target/method unavailable"

		for check in checks:
			var entry: Dictionary = check.duplicate(true)
			entry["stage"] = stage_id
			all_checks.append(entry)

		stage_results.append({"id": stage_id, "index": int(stage["index"]),
			"status": stage_status, "reason": stage_reason, "detail": stage_detail,
			"actions": action_log, "checks": checks, "waited_frames": waited,
			"window_frames": int(stage["window_frames"]),
			"action_frame": action_frame,
			"observed_frame": Engine.get_process_frames()})
		if stage_status == "PASS":
			completed.append(stage_id)
			continue
		status = stage_status
		reason = stage_reason
		detail = "stage %s: %s" % [stage_id, stage_detail]
		failed_stage = stage_id
		break

	# 只有整条链每一段都真实执行并成立才算 PASS。
	if status == "PASS" and completed.size() != stages.size():
		status = "INSUFFICIENT"
		reason = "stage_incomplete"
		detail = "only %d of %d stages completed" % [completed.size(), stages.size()]

	_finish(_with(base, {
		"status": status, "reason": reason, "detail": detail,
		"action_executed": action_executed and completed.size() == stages.size(),
		"preconditions": precondition_checks, "checks": all_checks,
		"stages": stage_results, "completed_stages": completed,
		"failed_stage": failed_stage,
		"signals": _signal_counts(), "frame_budget": budget,
	}))


func _with(base: Dictionary, extra: Dictionary) -> Dictionary:
	var out := base.duplicate(true)
	for key in extra:
		out[key] = extra[key]
	return out


func _normalize_res(path: String) -> String:
	var text := path.strip_edges().replace("\\", "/")
	if text.begins_with("res://"):
		text = text.substr("res://".length())
	return text


# ---------------------------------------------------------------- 契约校验

## 阶段校验与 Python 侧同一套规则（预算/夹具顺序/零帧规则），失败即 INVALID。
func _validate_stage(raw: Variant, index: int) -> Dictionary:
	if typeof(raw) != TYPE_DICTIONARY:
		return {"ok": false, "error": "stages[%d] must be a mapping" % index}
	var stage: Dictionary = raw
	var label := "stages[%d]" % index
	var stage_id := str(stage.get("id", ""))
	if stage_id == "" or stage_id != stage_id.to_lower():
		return {"ok": false, "error": "%s.id must be a lowercase identifier" % label}
	var limits: Dictionary = _composite.get("limits", {})
	var window := int(stage.get("window_frames", 30))
	if window < 1 or window > int(limits.get("max_window_frames", 0)):
		return {"ok": false, "error": "%s(%s).window_frames must be 1..%d" % [
			label, stage_id, int(limits.get("max_window_frames", 0))]}
	var raw_actions: Variant = stage.get("actions")
	if typeof(raw_actions) != TYPE_ARRAY or raw_actions.is_empty():
		return {"ok": false, "error": "%s(%s).actions must be a non-empty list" % [
			label, stage_id]}
	if raw_actions.size() > int(limits.get("max_actions_per_stage", 0)):
		return {"ok": false, "error": "%s(%s) declares too many actions" % [label, stage_id]}
	var actions: Array = []
	for position in raw_actions.size():
		var validated := _validate_action(raw_actions[position], position)
		if not bool(validated.get("ok", false)):
			return validated
		var action: Dictionary = validated["action"]
		if _denied.has(str(action.get("type", ""))):
			return {"ok": false, "error": "%s(%s) uses denied action %s" % [
				label, stage_id, str(action.get("type", ""))]}
		actions.append(action)
	var sequence := _check_action_sequence(actions)
	if not bool(sequence.get("ok", false)):
		return {"ok": false, "error": "%s(%s): %s" % [
			label, stage_id, str(sequence.get("error", ""))]}
	var raw_expected: Variant = stage.get("expected")
	if typeof(raw_expected) != TYPE_ARRAY or raw_expected.is_empty():
		return {"ok": false, "error": "%s(%s).expected must be a non-empty list" % [
			label, stage_id]}
	if raw_expected.size() > int(limits.get("max_checks_per_stage", 0)):
		return {"ok": false, "error": "%s(%s) declares too many checks" % [label, stage_id]}
	var expected: Array = []
	for position in raw_expected.size():
		var validated := _validate_check(raw_expected[position], position,
			"%s(%s).expected" % [label, stage_id])
		if not bool(validated.get("ok", false)):
			return validated
		expected.append(validated["check"])
	# 阶段级最小证据规则（Phase 1.45 零帧规则的组合形式）。
	if _frame_budget(actions) == 0 and not _contract_has_evidence(expected):
		return {"ok": false, "error": "%s(%s) asserts only the absence of behaviour while "
			% [label, stage_id] + "no action advances frames; the stage would pass without "
			+ "any observation window"}
	return {"ok": true, "stage": {"id": stage_id, "index": index, "actions": actions,
		"expected": expected, "window_frames": window, "frames": _frame_budget(actions)}}


## 夹具只能在行为动作之前 + 夹具数量 + 至少一个行为动作。
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
				return {"ok": false, "error": "actions[%d] is a fixture action but follows "
					% index + "a behavior action; setup must come first"}
		else:
			behaviors += 1
			seen_behavior = true
	if behaviors == 0:
		return {"ok": false, "error": "at least one non-fixture (behavior) action is required"}
	if fixtures > max_fixtures:
		return {"ok": false, "error": "%d fixture actions exceed the limit %d"
			% [fixtures, max_fixtures]}
	return {"ok": true}


func _frame_budget(actions: Array) -> int:
	var total := 0
	for action in actions:
		var spec: Dictionary = _manifest["actions"].get(str(action.get("type", "")), {})
		if bool(spec.get("advances_frames", false)):
			total += int(action.get("params", {}).get("frames", 0))
	return total


## 期望集是否含可观测的正面证据（与 Python 侧同一语义）。
func _contract_has_evidence(checks: Array) -> bool:
	for check in checks:
		var params: Dictionary = check.get("params", {})
		if str(check.get("check", "")) == "signal":
			if int(params.get("count", 0)) > 0:
				return true
			continue
		if not params.has("equals"):
			return true
		var value: Variant = params.get("equals")
		if typeof(value) != TYPE_BOOL:
			return true
		if bool(value):
			return true
	return false


func _validate_action(raw: Variant, index: int) -> Dictionary:
	var where := "actions[%d]" % index
	if typeof(raw) != TYPE_DICTIONARY:
		return {"ok": false, "error": "%s must be a mapping" % where}
	var action: Dictionary = raw
	var action_type := str(action.get("type", ""))
	if _denied.has(action_type):
		return {"ok": false, "error": "%s.type %s is denied by the composite protocol" % [
			where, action_type]}
	var spec: Dictionary = _manifest["actions"].get(action_type, {})
	if spec.is_empty():
		return {"ok": false, "error": "%s.type %s is not a registered action" % [
			where, action_type]}
	var implementation := str(spec.get("implementation", ""))
	if not bool(spec.get("implemented", false)) or not ACTION_IMPLEMENTATIONS.has(implementation):
		return {"ok": false, "error": "%s.type %s is not available in the composite probe"
			% [where, action_type]}
	var p := _validate_params(spec.get("params", {}), action.get("params", {}), where)
	if not bool(p.get("ok", false)):
		return p
	var target_kind := str(spec.get("target", "node"))
	var target := str(action.get("target", "."))
	if not _valid_target(target):
		return {"ok": false, "error": "%s.target %s is not a scene path" % [where, target]}
	if target_kind == "none" and target != "" and target != ".":
		return {"ok": false, "error": "%s.target %s is not allowed (target kind none)"
			% [where, target]}
	return {"ok": true, "action": {"type": action_type, "target": target,
		"params": p["values"], "implementation": implementation,
		"fixture": bool(spec.get("fixture", false)),
		"advances_frames": bool(spec.get("advances_frames", false)),
		"target_kind": target_kind}}


func _validate_check(raw: Variant, index: int, where: String) -> Dictionary:
	var label := "%s[%d]" % [where, index]
	if typeof(raw) != TYPE_DICTIONARY:
		return {"ok": false, "error": "%s must be a mapping" % label}
	var entry: Dictionary = raw
	var check := str(entry.get("check", ""))
	var spec: Dictionary = _manifest["observations"].get(check, {})
	if spec.is_empty():
		return {"ok": false, "error": "%s.check %s is not a registered check" % [label, check]}
	var implementation := str(spec.get("implementation", ""))
	if not bool(spec.get("implemented", false)) \
			or not OBSERVATION_IMPLEMENTATIONS.has(implementation):
		return {"ok": false, "error": "%s.check %s is not available in the composite probe"
			% [label, check]}
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
		var signal_spec: Dictionary = _manifest["signals"].get(str(params["entry"]), {})
		if signal_spec.is_empty():
			return {"ok": false, "error": "%s.params.entry %s is not a registered signal" % [
				label, str(params["entry"])]}
		if params.has("last_args"):
			var declared: Array = signal_spec.get("args", [])
			var args: Array = params["last_args"]
			if args.size() > declared.size():
				return {"ok": false, "error": "%s.params.last_args has too many arguments"
					% label}
			for position in args.size():
				if not _type_matches(str(declared[position]), args[position]):
					return {"ok": false, "error": "%s.params.last_args[%d] type mismatch"
						% [label, position]}
	else:
		var result_type := str(spec.get("result", {}).get("type", ""))
		if params.has("equals") and not _type_matches(result_type, params["equals"]):
			return {"ok": false, "error": "%s.params.equals does not match result type %s"
				% [label, result_type]}
		if params.has("tolerance") and not params.has("equals"):
			return {"ok": false, "error": "%s.params.tolerance requires equals" % label}
		if params.has("min") and params.has("max") \
				and float(params["min"]) > float(params["max"]):
			return {"ok": false, "error": "%s.params.min must be <= max" % label}
		if result_type == "float" and not params.has("equals") \
				and not params.has("min") and not params.has("max"):
			return {"ok": false, "error": "%s declares neither equals nor min/max" % label}
	return {"ok": true, "check": {"check": check, "target": target, "params": params,
		"implementation": implementation,
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
		if not _param_value_ok(provided[name], spec):
			return {"ok": false, "error": "%s.params.%s does not match type %s" % [
				where, name, str(spec.get("type", ""))]}
		normalized[name] = provided[name]
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
	if target == "" or target == ".":
		return true
	if target.contains("..") or target.begins_with("/") or target.contains("\\"):
		return false
	return true


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


## Phase 1.52：与 feature_behavior_probe 同名实现保持语义一致（Cooldown.start）。
func _impl_cooldown_start(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not node.has_method("start"):
		record["error"] = "target cannot start a cooldown"
		return record
	var ok_started: bool = node.call("start", float(params.get("duration", 0.0)))
	record["executed"] = true
	record["accepted"] = ok_started
	return record


## Phase 1.52：与 feature_behavior_probe 同名实现保持语义一致（ScreenShake.add_trauma）。
func _impl_screenshake_add_trauma(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not node.has_method("add_trauma"):
		record["error"] = "target cannot add trauma"
		return record
	var accepted: bool = node.call("add_trauma", float(params.get("amount", 0.0)))
	record["executed"] = true
	record["accepted"] = accepted
	return record


## Phase 1.53：与 feature_behavior_probe 同名实现保持语义一致（StateMachine.start）。
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


## Phase 1.53：与 feature_behavior_probe 同名实现保持语义一致（StateMachine.transition_to）。
func _impl_statemachine_transition_to(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not node.has_method("transition_to"):
		record["error"] = "target is not a StateMachine"
		return record
	node.call("transition_to", str(params.get("state_name", "")))
	record["executed"] = true
	record["accepted"] = true
	return record


## Phase 1.53：与 feature_behavior_probe 同名实现保持语义一致（SaveGame.save_to_slot）。
func _impl_savegame_save_slot(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not node.has_method("save_to_slot"):
		record["error"] = "target is not a SaveGame"
		return record
	var accepted: bool = node.call("save_to_slot", str(params.get("slot", "")))
	record["executed"] = true
	record["accepted"] = accepted
	return record


## Phase 1.53：与 feature_behavior_probe 同名实现保持语义一致（SaveGame.load_from_slot）。
func _impl_savegame_load_slot(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not node.has_method("load_from_slot"):
		record["error"] = "target is not a SaveGame"
		return record
	var accepted: bool = node.call("load_from_slot", str(params.get("slot", "")))
	record["executed"] = true
	record["accepted"] = accepted
	return record


## Phase 1.53：与 feature_behavior_probe 同名实现保持语义一致（AttackEmitter.do_attack）。
func _impl_attackemitter_do_attack(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not node.has_method("do_attack"):
		record["error"] = "target is not an AttackEmitter"
		return record
	node.call("do_attack")
	record["executed"] = true
	record["accepted"] = true
	return record


## Phase 1.54：与 feature_behavior_probe 同名实现保持语义一致（Knockback.apply）。
func _impl_knockback_apply(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not node.has_method("apply"):
		record["error"] = "target cannot apply knockback"
		return record
	var direction := Vector2(float(params.get("dir_x", 0.0)), float(params.get("dir_y", 0.0)))
	var accepted: bool = node.call("apply", direction, float(params.get("force", 0.0)))
	record["executed"] = true
	record["accepted"] = accepted
	return record


## Phase 1.54：与 feature_behavior_probe 同名实现保持语义一致（SfxPool.play）。
## 播放载荷由探针内部构造（短静音 AudioStreamWAV）。
func _impl_sfx_play(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not node.has_method("play"):
		record["error"] = "target cannot play sfx"
		return record
	var wav := AudioStreamWAV.new()
	# 60 秒静音（8000Hz）：Dummy 驱动按墙钟混音，短流会在高负载窗口内放完；
	# 60s >> 任何观测窗口，簿记确定。
	wav.data = PackedByteArray()
	wav.data.resize(480000)
	wav.format = AudioStreamWAV.FORMAT_8_BITS
	wav.mix_rate = 8000
	var accepted: bool = node.call("play", wav)
	record["executed"] = true
	record["accepted"] = accepted
	return record


## 受控帧推进：真实 physics 帧（固定 delta）。
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


## 受控物理接触：在目标**全局位置**生成真实 CharacterBody2D（可带真实 Health），
## 由后续物理帧触发 Area2D.body_entered；不调用任何私有回调、不改写被测状态。
func _impl_physics_overlap(node: Node, params: Dictionary, record: Dictionary) -> Dictionary:
	if node == null or not (node is Node2D):
		record["error"] = "physics.overlap target is not a Node2D in the tree"
		return record
	var group := str(params.get("group", ""))
	if group == "":
		record["error"] = "physics.overlap requires params.group"
		return record

	var body := CharacterBody2D.new()
	body.name = "CompositeActor%d" % _actors.size()
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
	var point := (node as Node2D).global_position
	root.add_child(body)
	body.global_position = point
	_actors.append(body)

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
		var params: Dictionary = entry.get("params", {})
		var signal_spec: Dictionary = _manifest["signals"].get(str(params.get("entry", "")), {})
		if signal_spec.is_empty():
			continue
		var node := _resolve(str(entry.get("target", ".")))
		if node == null:
			continue
		var signal_name := str(signal_spec.get("signal", ""))
		var watch_key := str(node.get_instance_id()) + "|" + signal_name
		if _signal_connects.has(watch_key):
			continue
		if not node.has_signal(signal_name):
			continue
		_signals[watch_key] = []
		var callback := func(a = null, b = null, c = null, d = null) -> void:
			_record_signal(watch_key, [a, b, c, d])
		node.connect(signal_name, callback)
		_signal_connects[watch_key] = true


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


## 位移基线 = 本阶段动作前的真实位置；不根据预期值反推。每阶段重新采集。
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
		var allows_missing := implementation == "observe_node_exists"
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


## Phase 1.52：Cooldown.is_ready() —— 与单 Feature 探针同语义的只读观测。
func _observe_cooldown_is_ready(node: Node, _entry: Dictionary) -> Dictionary:
	if node == null or not node.has_method("is_ready"):
		return {"available": false}
	return {"available": true, "observed": bool(node.call("is_ready"))}


## Phase 1.53：StateMachine 当前状态名。只读，与单 Feature 探针同语义。
func _observe_statemachine_current_state_name(node: Node, _entry: Dictionary) -> Dictionary:
	if node == null or not ("current_state" in node):
		return {"available": false}
	var current = node.get("current_state")
	if current == null or not is_instance_valid(current):
		return {"available": true, "observed": ""}
	return {"available": true, "observed": String(current.name)}


## Phase 1.53：SaveGame 最近写入的槽位名。只读，与单 Feature 探针同语义。
func _observe_savegame_last_slot(node: Node, _entry: Dictionary) -> Dictionary:
	if node == null or not node.has_method("get_last_slot"):
		return {"available": false}
	return {"available": true, "observed": String(node.call("get_last_slot"))}


## Phase 1.54：SfxPool 占用数。只读自管簿记，与单 Feature 探针同语义。
func _observe_sfx_pool_active_count(node: Node, _entry: Dictionary) -> Dictionary:
	if node == null or not node.has_method("active_count"):
		return {"available": false}
	return {"available": true, "observed": int(node.call("active_count"))}


## Phase 1.50：与单 Feature 探针同语义的只读观测（共享协议要求两端能力一致）。
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
	return {"available": true, "observed": point.x if str(params.get("axis", "x")) == "x"
		else point.y}


func _observe_node2d_displacement(node: Node, entry: Dictionary) -> Dictionary:
	if node == null or not (node is Node2D):
		return {"available": false}
	var target_path := str(entry.get("target", "."))
	if not _baselines.has(target_path):
		return {"available": false}
	var params: Dictionary = entry.get("params", {})
	var base: Vector2 = _baselines[target_path]
	var delta := (node as Node2D).global_position - base
	return {"available": true, "observed": delta.x if str(params.get("axis", "x")) == "x"
		else delta.y}


func _observe_signal(node: Node, entry: Dictionary) -> Dictionary:
	var params: Dictionary = entry.get("params", {})
	var signal_spec: Dictionary = _manifest["signals"].get(str(params.get("entry", "")), {})
	if node == null or signal_spec.is_empty():
		return {"available": false}
	if not node.has_signal(str(signal_spec.get("signal", ""))):
		return {"available": false}
	var watch_key := str(node.get_instance_id()) + "|" + str(signal_spec.get("signal", ""))
	if not _signals.has(watch_key):
		return {"available": false}
	return {"available": true, "observed": _signals[watch_key].size()}


func _resolve(target: String) -> Node:
	if target == "" or target == ".":
		return _scene
	if _scene == null or not is_instance_valid(_scene):
		return null
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
