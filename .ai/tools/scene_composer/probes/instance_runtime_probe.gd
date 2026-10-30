extends SceneTree
## Runtime Instance Evidence Probe（Phase 1.39）
##
## 真实加载场景 → 等待观察时机 → 遍历**加载后的对象树** → 核对契约 → 写机器可读结果。
##
## 用法：
##   godot --headless --path <project> -s res://.ai/tools/scene_composer/probes/instance_runtime_probe.gd \
##         -- --contract=<abs json> --result=<abs json>
##
## 契约（JSON，由 runtime_instance_evidence.py 生成）：
##   scene             res:// 场景路径
##   when              after_load | after_frames:<N> | after_action:<name>
##   timeout_frames    0 = 不轮询；>0 = 轮询窗口帧数
##   expectations[]    {id, path? | parent?, type, count, runtime?}
##   run_id            可追踪运行标识
##
## 结果（JSON，同时以 EVIDENCE_RESULT: 单行输出）：
##   status            PASS | MISMATCH | INSUFFICIENT | INVALID
##   reason            load_error | missing | missing_after_timeout | type_mismatch |
##                     count_mismatch | action_not_triggerable | probe_error
##   checks[]          {id, path, type, expected_count, found_count, found_paths,
##                      status, runtime, first_seen_frame}
##   observed_frame / waited_frames / node_count / scene / run_id
##
## 约束：
##   - 只读场景，不修改项目、不写场景文件；只写 --result 指定的 JSON。
##   - 不伪造 PASS：加载失败 / 无法采集 → 非 PASS。
##   - 不自动触发游戏内动作：`after_action:*` 直接返回 INSUFFICIENT（由调用方决定）。

const RESULT_PREFIX := "EVIDENCE_RESULT: "
const EXIT_OK := 0
const EXIT_INPUT := 2
const SETTLE_FRAMES := 2

var _contract_path := ""
var _result_path := ""


func _initialize() -> void:
	_parse_args()
	if _contract_path == "" or _result_path == "":
		_finish({"status": "INVALID", "reason": "probe_error",
			"detail": "missing --contract/--result"}, EXIT_INPUT)
		return
	var contract: Variant = _read_json(_contract_path)
	if typeof(contract) != TYPE_DICTIONARY or contract.is_empty():
		_finish({"status": "INVALID", "reason": "probe_error",
			"detail": "contract unreadable: " + _contract_path}, EXIT_INPUT)
		return
	await _run(contract)
	quit(EXIT_OK)


func _parse_args() -> void:
	for arg in OS.get_cmdline_user_args():
		var text := str(arg)
		if text.begins_with("--contract="):
			_contract_path = text.substr("--contract=".length())
		elif text.begins_with("--result="):
			_result_path = text.substr("--result=".length())


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


func _finish(payload: Dictionary, code: int) -> void:
	var written := _write_json(_result_path, payload)
	if written:
		print(RESULT_PREFIX + JSON.stringify(payload))
	else:
		printerr("EVIDENCE_PROBE_ERROR: cannot write result to " + _result_path)
	quit(code)


func _run(contract: Dictionary) -> void:
	var scene_path := str(contract.get("scene", ""))
	var run_id := str(contract.get("run_id", ""))
	var expected_when := str(contract.get("when", "after_load"))
	var timeout_frames := int(contract.get("timeout_frames", 0))
	var expectations: Array = contract.get("expectations", [])

	if scene_path == "" or expectations.is_empty():
		_finish({"status": "INVALID", "reason": "probe_error",
			"detail": "contract requires scene and expectations",
			"scene": scene_path, "run_id": run_id}, EXIT_OK)
		return
	if expected_when.begins_with("after_action:"):
		# 不自动触发游戏动作：交给调用方判定为 INSUFFICIENT。
		_finish({"status": "INSUFFICIENT", "reason": "action_not_triggerable",
			"detail": "contract requires an action: " + expected_when,
			"scene": scene_path, "run_id": run_id}, EXIT_OK)
		return

	var packed: PackedScene = ResourceLoader.load(scene_path, "PackedScene",
		ResourceLoader.CACHE_MODE_IGNORE)
	if packed == null:
		_finish({"status": "MISMATCH", "reason": "load_error",
			"detail": "Failed to load scene: " + scene_path,
			"scene": scene_path, "run_id": run_id, "checks": []}, EXIT_OK)
		return

	var instance: Node = packed.instantiate()
	if instance == null:
		_finish({"status": "MISMATCH", "reason": "load_error",
			"detail": "Failed to instantiate scene: " + scene_path,
			"scene": scene_path, "run_id": run_id, "checks": []}, EXIT_OK)
		return

	root.add_child(instance)
	for _i in SETTLE_FRAMES:
		await process_frame

	# 观察时机：after_frames:<N> 先等 N 帧（after_load 只等稳定帧）。
	var target_frames := 0
	if expected_when.begins_with("after_frames:"):
		target_frames = max(0, int(expected_when.substr("after_frames:".length())))
	while target_frames > 0:
		await process_frame
		target_frames -= 1
	var observed_frame := Engine.get_process_frames()

	var snapshot := _snapshot(instance)
	var checks := _evaluate(expectations, snapshot, 0, [])

	# 轮询窗口：只为尚未满足的期望等待（不在动作前误判缺失）。
	var waited := 0
	if timeout_frames > 0:
		while waited < timeout_frames and not _all_pass(checks):
			await process_frame
			waited += 1
			snapshot = _snapshot(instance)
			checks = _evaluate(expectations, snapshot, waited, checks)

	var payload := {
		"scene": scene_path,
		"run_id": run_id,
		"expected_when": expected_when,
		"observed_frame": observed_frame,
		"waited_frames": waited,
		"timeout_frames": timeout_frames,
		"node_count": snapshot.size(),
		"checks": checks,
	}
	payload["status"] = _status_for(checks)
	payload["reason"] = _reason_for(checks, timeout_frames)
	_finish(payload, EXIT_OK)


func _snapshot(scene_root: Node) -> Array:
	var out: Array = []
	_walk(scene_root, ".", "", out)
	return out


func _walk(node: Node, path: String, parent_path: String, out: Array) -> void:
	out.append({
		"path": path,
		"parent": parent_path,
		"name": str(node.name),
		"type": node.get_class(),
	})
	for child in node.get_children():
		var child_path := str(child.name) if path == "." else path + "/" + str(child.name)
		_walk(child, child_path, path, out)


func _evaluate(expectations: Array, snapshot: Array, frame: int, previous: Array) -> Array:
	var checks: Array = []
	var first_seen := {}
	for old in previous:
		if typeof(old) == TYPE_DICTIONARY and int(old.get("first_seen_frame", -1)) >= 0:
			first_seen[str(old.get("id", ""))] = int(old.get("first_seen_frame"))
	for raw in expectations:
		if typeof(raw) != TYPE_DICTIONARY:
			continue
		var entry: Dictionary = raw
		var check_id := str(entry.get("id", ""))
		var expected_type := str(entry.get("type", ""))
		var expected_count := int(entry.get("count", 1))
		var path := str(entry.get("path", ""))
		var parent := str(entry.get("parent", ""))
		var runtime_flag := bool(entry.get("runtime", false))

		var matches: Array = []
		if path != "":
			for node_entry in snapshot:
				if str(node_entry.get("path", "")) == path:
					matches.append(node_entry)
					break
		elif parent != "":
			for node_entry in snapshot:
				if str(node_entry.get("parent", "")) == parent:
					matches.append(node_entry)

		var typed: Array = []
		for node_entry in matches:
			if _type_matches(str(node_entry.get("type", "")), expected_type):
				typed.append(node_entry)

		var status := "PASS"
		var found_paths: Array = []
		for node_entry in typed:
			found_paths.append(str(node_entry.get("path", "")))
		if path != "":
			# 路径契约：节点不存在 = MISSING；存在但类型不符 = TYPE_MISMATCH。
			if matches.is_empty():
				status = "MISSING"
			elif typed.is_empty():
				status = "TYPE_MISMATCH"
			elif typed.size() != expected_count:
				status = "COUNT_MISMATCH"
		else:
			# 类型/父节点契约：同类节点不存在 = MISSING；数量不符 = COUNT_MISMATCH。
			if typed.is_empty():
				status = "MISSING"
			elif typed.size() != expected_count:
				status = "COUNT_MISMATCH"

		var seen_frame := -1
		if status == "PASS":
			seen_frame = int(first_seen.get(check_id, frame))
		checks.append({
			"id": check_id,
			"path": path,
			"parent": parent,
			"type": expected_type,
			"expected_count": expected_count,
			"found_count": typed.size(),
			"found_paths": found_paths,
			"actual_types": _types_of(matches),
			"status": status,
			"runtime": runtime_flag,
			"first_seen_frame": seen_frame,
		})
	return checks


func _types_of(entries: Array) -> Array:
	var types: Array = []
	for entry in entries:
		types.append(str(entry.get("type", "")))
	return types


func _type_matches(actual: String, expected: String) -> bool:
	if actual == expected:
		return true
	if not ClassDB.class_exists(expected):
		return false
	# 继承关系也算匹配（契约写 PhysicsBody2D 时 Area2D 合法）。
	return ClassDB.is_parent_class(actual, expected)


func _all_pass(checks: Array) -> bool:
	for check in checks:
		if str(check.get("status", "")) != "PASS":
			return false
	return true


func _status_for(checks: Array) -> String:
	if checks.is_empty():
		return "INVALID"
	for check in checks:
		if str(check.get("status", "")) != "PASS":
			return "MISMATCH"
	return "PASS"


func _reason_for(checks: Array, timeout_frames: int) -> String:
	for check in checks:
		var status := str(check.get("status", ""))
		if status == "TYPE_MISMATCH":
			return "type_mismatch"
		if status == "COUNT_MISMATCH":
			return "count_mismatch"
	for check in checks:
		if str(check.get("status", "")) == "MISSING":
			if bool(check.get("runtime", false)):
				return "missing_after_timeout" if timeout_frames > 0 else "missing"
			return "missing"
	return ""
