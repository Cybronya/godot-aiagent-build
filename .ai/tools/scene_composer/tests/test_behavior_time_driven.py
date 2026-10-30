#!/usr/bin/env python3
"""时间驱动行为能力测试（Phase 1.42）

Phase 1.41 把「允许什么」收敛到 `.ai/context/behavior_protocol.yaml`；本阶段在同一份
协议里加入**受控帧推进**、**受约束的状态设置**与**时间点观测**，并用真实 Godot 运行时
验证第一批时间驱动 Feature。本测试锁定：

    Case 1  帧推进基元：帧号账本与位移随时间线性变化（真实 physics 帧）
    Case 2  状态设置受限：白名单属性 / 合法值 / before-after 记录 / 夹具顺序
    Case 3  帧与参数预算：非法帧数、超上限、非法帧类型、帧类型 none 的目标
    Case 4  Python 与 Godot 对新增能力的非法输入给出兼容拒绝
    Case 5  时间驱动 Feature 的真实证据：3 个 Feature / 6 个 behavior 双次重放一致
    Case 6  负向对照：真实缺陷 / 窗口耗尽 / 观测不可用 / 协议漂移 / CLI 退出码
    Case 7  既有 6 个 behavior 语义不变（观测值与重放结果）

每项负向对照都在隔离副本内进行，结束后比对 sha256 恢复原状；不修改仓库场景、
不写黄金基线、不提交 git。

用法:
    python .ai/tools/scene_composer/tests/test_behavior_time_driven.py
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
TOOL_DIR = os.path.dirname(_HERE)
TOOLS_DIR = os.path.dirname(TOOL_DIR)
DOTAI = os.path.dirname(TOOLS_DIR)
PROJECT_ROOT = os.path.dirname(DOTAI)
FEATURES = os.path.join(PROJECT_ROOT, "Features")
CLI = os.path.join(TOOL_DIR, "feature_behavior_evidence.py")

for path in (TOOL_DIR, TOOLS_DIR, _HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import behavior_protocol                                          # noqa: E402
import feature_behavior_evidence as behavior                      # noqa: E402
import runtime_instance_evidence as runtime_evidence              # noqa: E402

_failures = []
_godot = ""
_tempdir = ""

PLATFORM_SCENE = "res://Features/moving_platform/MovingPlatform.tscn"
TRIGGER_SCENE = "res://Features/trigger_switch/trigger_switch.tscn"
PLAYER_SCENE = "res://Features/player_movement/Player.tscn"
DOOR_SCENE = "res://Features/openable_door/OpenableDoor.tscn"


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def write_text(path: str, text: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe(actions, expected, scene=PLATFORM_SCENE, window_frames=1,
          preconditions=None, feature="probe", behavior_id="case", tag=""):
    """跑一次真实探针，返回原始结果字典（不做判定）。"""
    contract = {"feature": feature, "behavior": behavior_id,
                "run_id": "td-%s-%s" % (behavior_id, tag or actions[0].get("type", "x")),
                "replay_index": 1, "window_frames": window_frames, "scene": scene,
                "actions": actions, "preconditions": preconditions or [],
                "expected": expected}
    observation = behavior.run_probe(contract, PROJECT_ROOT, _godot, timeout_s=60)
    return observation.get("result") or {}


def range_check(check, axis, low=None, high=None):
    entry = {"check": check, "target": ".", "axis": axis}
    if low is not None:
        entry["min"] = low
    if high is not None:
        entry["max"] = high
    return entry


def advance(frames):
    return {"type": "simulation.advance_frames", "params": {"frames": frames}}


def build_feature(name: str, behavior_block):
    """在临时 Features 目录写一个只含 behavior 声明的模板并跑 Python 契约校验。"""
    features = os.path.join(_tempdir, "contracts")
    directory = os.path.join(features, name)
    body = yaml.safe_dump(behavior_block, allow_unicode=True, sort_keys=False)
    write_text(os.path.join(directory, "template.yaml"),
               "feature:\n  id: %s\nscene:\n  source: Probe.tscn\nbehavior:\n%s"
               % (name, textwrap.indent(body, "  ")))
    contracts, reports = behavior.build_contracts(name, features)
    return contracts, reports


def rejected_by_python(name: str, behavior_block, needle: str = "") -> None:
    contracts, reports = build_feature(name, behavior_block)
    detail = reports[0].detail if reports else "contract accepted"
    ok("case3/2: %s rejected by the contract validator" % name,
       not contracts and bool(reports) and reports[0].status == behavior.STATUS_INVALID
       and needle in detail, detail)


def rejected_by_godot(name: str, actions, expected, scene=PLATFORM_SCENE,
                      preconditions=None) -> dict:
    payload = probe(actions, expected, scene=scene, preconditions=preconditions,
                    behavior_id=name, tag=name)
    ok("case4: %s rejected by Godot as INVALID/contract_invalid" % name,
       payload.get("status") == "INVALID" and payload.get("reason") == "contract_invalid",
       json.dumps(payload)[:300])
    ok("case4: %s never becomes PASS" % name, payload.get("status") != "PASS")
    return payload


def copied_features(tag: str) -> str:
    target = os.path.join(_tempdir, "features_" + tag, "Features")
    shutil.copytree(FEATURES, target)
    return target


def patch(path: str, old: str, new: str) -> bytes:
    with open(path, "rb") as handle:
        original = handle.read()
    text = original.decode("utf-8")
    if old not in text:
        raise AssertionError("patch anchor not found in %s" % path)
    write_text(path, text.replace(old, new, 1))
    return original


def restore(path: str, original: bytes) -> None:
    with open(path, "wb") as handle:
        handle.write(original)


def main() -> int:
    global _godot, _tempdir
    _godot = runtime_evidence.find_godot(PROJECT_ROOT)
    if not _godot:
        print("SKIP: godot executable not found; time-driven behavior cannot be verified")
        return 1
    os.makedirs(os.path.join(DOTAI, "tmp"), exist_ok=True)
    _tempdir = tempfile.mkdtemp(prefix="time_driven_", dir=os.path.join(DOTAI, "tmp"))
    try:
        run_cases()
    finally:
        shutil.rmtree(_tempdir, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all time-driven behavior checks passed")
    return 0


def run_cases() -> None:
    protocol = behavior_protocol.load_protocol()

    # ---------------- Case 1: 帧推进基元 ----------------
    print("=== Case 1: advance_frames moves real physics time ===")
    wide = [range_check("node2d.displacement", "x", -10000.0, 10000.0)]
    sixty = probe([advance(60)], wide, behavior_id="adv60", tag="adv60")
    twelve = probe([advance(12)], wide, behavior_id="adv12", tag="adv12")
    observed_60 = (sixty.get("checks") or [{}])[0].get("observed")
    observed_12 = (twelve.get("checks") or [{}])[0].get("observed")
    ok("case1: 60 physics frames move the platform ~100 px",
       isinstance(observed_60, (int, float)) and 98.0 <= observed_60 <= 102.0,
       str(observed_60))
    ok("case1: 12 physics frames move it ~20 px (linear in frames)",
       isinstance(observed_12, (int, float)) and 18.0 <= observed_12 <= 22.0,
       str(observed_12))
    ledger = (sixty.get("actions") or [{}])[0]
    ok("case1: each action records its own physics frame span",
       ledger.get("advanced_frames") == 60
       and isinstance(ledger.get("started_frame"), int)
       and ledger.get("ended_frame", 0) - ledger.get("started_frame", 0) == 60,
       json.dumps(ledger)[:300])
    ok("case1: the run records its own frame bookkeeping",
       sixty.get("advanced_frames") == 60 and sixty.get("frame_budget") == 61
       and isinstance(sixty.get("observed_physics_frame"), int),
       json.dumps({key: sixty.get(key) for key in
                   ("advanced_frames", "frame_budget", "observed_physics_frame")}))
    baseline = (sixty.get("baselines") or {}).get(".", {})
    ok("case1: displacement is measured from a real pre-action baseline",
       isinstance(baseline.get("x"), (int, float))
       and isinstance(baseline.get("y"), (int, float))
       and abs(float(baseline.get("y", 999))) < 0.5
       and 0.0 <= float(baseline.get("x", -1)) < 200.0, json.dumps(baseline))
    too_big = probe([advance(301)], wide, behavior_id="adv301", tag="adv301")
    ok("case1: 301 frames (over the protocol maximum) is rejected",
       too_big.get("status") == "INVALID", json.dumps(too_big)[:200])

    # ---------------- Case 2: 受约束状态设置 ----------------
    print("=== Case 2: constrained state setup is a bounded fixture ===")
    fixture = probe([
        {"type": "state.set_property", "target": ".",
         "params": {"property": "trigger_switch.trigger_mode", "value": "Toggle"}},
        advance(1),
    ], [{"check": "trigger.is_triggered", "target": ".", "equals": False},
        {"check": "node.exists", "target": ".", "equals": True}],
        scene=TRIGGER_SCENE, behavior_id="fixture", tag="fixture")
    record = (fixture.get("actions") or [{}])[0]
    ok("case2: the declared property is set through the fixture action",
       fixture.get("status") == "PASS" and record.get("fixture") is True
       and record.get("property") == "trigger_switch.trigger_mode"
       and record.get("before") == 0 and record.get("value") == "Toggle"
       and record.get("after") == 2,
       json.dumps(record)[:300])

    rejected_by_python("undeclared_property", [{
        "id": "x",
        "actions": [{"type": "state.set_property", "target": ".",
                     "params": {"property": "door.is_open", "value": True}},
                    advance(1)],
        "expected": [{"check": "node.exists", "target": ".", "equals": True}],
    }], "not a registered property")
    rejected_by_python("bad_property_value", [{
        "id": "x",
        "actions": [{"type": "state.set_property", "target": ".",
                     "params": {"property": "trigger_switch.trigger_mode",
                                "value": "Bogus"}},
                    advance(1)],
        "expected": [{"check": "node.exists", "target": ".", "equals": True}],
    }], "not an allowed value")
    rejected_by_python("fixture_after_behavior", [{
        "id": "x",
        "actions": [advance(1),
                    {"type": "state.set_property", "target": ".",
                     "params": {"property": "trigger_switch.trigger_mode",
                                "value": "Toggle"}}],
        "expected": [{"check": "node.exists", "target": ".", "equals": True}],
    }], "setup must come first")
    rejected_by_python("fixtures_only", [{
        "id": "x",
        "actions": [{"type": "state.set_property", "target": ".",
                     "params": {"property": "trigger_switch.trigger_mode",
                                "value": "Toggle"}}],
        "expected": [{"check": "node.exists", "target": ".", "equals": True}],
    }], "at least one non-fixture")

    rejected_by_godot("godot_fixture_after_behavior",
                      [advance(1),
                       {"type": "state.set_property", "target": ".",
                        "params": {"property": "trigger_switch.trigger_mode",
                                   "value": "Toggle"}}],
                      wide, scene=TRIGGER_SCENE)
    rejected_by_godot("godot_bad_property_value",
                      [{"type": "state.set_property", "target": ".",
                        "params": {"property": "trigger_switch.trigger_mode",
                                   "value": "Bogus"}}],
                      wide, scene=TRIGGER_SCENE)
    wrong_class = probe([{"type": "state.set_property", "target": ".",
                          "params": {"property": "trigger_switch.trigger_mode",
                                     "value": "Toggle"}}],
                        wide, scene=DOOR_SCENE, behavior_id="wrong_class",
                        tag="wrong_class")
    ok("case2: setting a declared property on the wrong class never passes",
       wrong_class.get("status") in ("INSUFFICIENT", "INVALID")
       and wrong_class.get("status") != "PASS", json.dumps(wrong_class)[:300])

    # ---------------- Case 3: 帧/参数/预算 ----------------
    print("=== Case 3: frame and parameter budgets are enforced ===")
    expect = [{"check": "node.exists", "target": ".", "equals": True}]
    for name, block, needle in (
        ("zero_frames", [{"id": "x", "actions": [advance(0)], "expected": expect}],
         "does not match type int"),
        ("frames_over_per_action",
         [{"id": "x", "actions": [advance(700)], "expected": expect}],
         "does not match type int"),
        ("process_phase",
         [{"id": "x", "actions": [{"type": "simulation.advance_frames",
                                   "params": {"frames": 5, "phase": "process"}}],
           "expected": expect}], "does not match type enum"),
        ("frame_budget",
         [{"id": "x", "actions": [advance(300), advance(300)], "window_frames": 30,
           "expected": expect}], "exceeds max_total_frames"),
        ("target_kind_none",
         [{"id": "x", "actions": [{"type": "simulation.advance_frames", "target": "Child",
                                   "params": {"frames": 5}}], "expected": expect}],
         "target kind none"),
    ):
        rejected_by_python(name, block, needle)
    rejected_by_godot("godot_zero_frames", [advance(0)], wide)
    rejected_by_godot("godot_frames_over_limit", [advance(301)], wide)
    rejected_by_godot("godot_unknown_input_action",
                      [{"type": "input.press", "params": {"action": "move_nowhere"}},
                       advance(1)], wide, scene=PLAYER_SCENE)
    budget = protocol.frame_budget_errors(
        [{"type": "simulation.advance_frames", "params": {"frames": 300}},
         {"type": "simulation.advance_frames", "params": {"frames": 300}}], 30)
    ok("case3: the Python budget errors explain the overrun",
       budget and "600" in budget[0], str(budget))

    # ---------------- Case 4: Python / Godot 一致 ----------------
    print("=== Case 4: Python and Godot agree on the new capabilities ===")
    for name, actions, scene in (
        ("unknown_observation", [advance(1)], PLATFORM_SCENE),
    ):
        rejected_by_godot(name, actions,
                          [{"check": "node2d.velocity", "target": ".", "axis": "x",
                            "min": 0.0}], scene=scene)
    for name, check in (
        ("float_without_comparator", {"check": "node2d.position", "target": ".",
                                      "axis": "x"}),
        ("tolerance_without_equals", {"check": "node2d.position", "target": ".",
                                      "axis": "x", "tolerance": 1.0, "min": 0.0}),
        ("inverted_range", {"check": "node2d.position", "target": ".", "axis": "x",
                            "min": 5.0, "max": 1.0}),
        ("unknown_axis", {"check": "node2d.position", "target": ".", "axis": "z",
                          "min": 0.0}),
    ):
        errors = protocol.validate_check(check, 0, "expected")[1]
        payload = probe([advance(1)], [check], behavior_id=name, tag=name)
        ok("case4: %s rejected by Python" % name, bool(errors), str(errors))
        ok("case4: %s rejected by Godot as INVALID" % name,
           payload.get("status") == "INVALID", json.dumps(payload)[:300])

    # ---------------- Case 5: 真实时间驱动证据 ----------------
    print("=== Case 5: time-driven behaviors pass with two consistent replays ===")
    workspace = behavior.BehaviorWorkspace(FEATURES, _godot)
    reports = {}
    try:
        for feature in ("moving_platform", "trigger_switch", "player_movement"):
            for report in behavior.verify_feature(feature, FEATURES, FEATURES, _godot,
                                                  replay=2, workspace=workspace):
                reports[(report.feature, report.behavior)] = report
    finally:
        workspace.close()
    expected_behaviors = {
        ("moving_platform", "travel"), ("moving_platform", "round_trip"),
        ("trigger_switch", "latch_once"), ("trigger_switch", "toggle_on_second_contact"),
        ("player_movement", "move_right"), ("player_movement", "stop_on_release"),
    }
    ok("case5: all six time-driven behaviors reported", set(reports) == expected_behaviors,
       str(sorted(reports)))
    for key in sorted(expected_behaviors):
        report = reports.get(key)
        ok("case5: %s/%s PASS with consistent replays" % key,
           report is not None and report.status == behavior.STATUS_PASS
           and report.replay_count == 2 and report.replay_consistent,
           json.dumps(report.to_dict())[:400] if report else "missing")
    def axis_values(report):
        """同名的 x/y 位移检查用 expected 形状区分（区间 → x，equals → y）。"""
        values = {}
        for check in report.actual:
            if check.get("check") != "node2d.displacement":
                continue
            values["x" if isinstance(check.get("expected"), dict) else "y"] = \
                check.get("observed")
        return values

    travel = reports.get(("moving_platform", "travel"))
    if travel:
        measured = axis_values(travel)
        ok("case5: the platform really travelled ~100 px (not derived from the contract)",
           isinstance(measured["x"], (int, float))
           and 98.0 <= float(measured["x"]) <= 102.0, str(measured))
    player = reports.get(("player_movement", "move_right"))
    if player:
        measured = axis_values(player)
        ok("case5: input-driven movement really covered ~44 px",
           isinstance(measured.get("x"), (int, float))
           and 43.0 <= float(measured["x"]) <= 45.0, str(measured))

    # ---------------- Case 6: 负向对照 ----------------
    print("=== Case 6: real defects, exhausted windows and drift are caught ===")
    scripts = {
        "platform": os.path.join(FEATURES, "moving_platform", "moving_platform.gd"),
        "trigger": os.path.join(FEATURES, "trigger_switch", "trigger_switch.gd"),
    }
    baseline = {name: sha256(path) for name, path in scripts.items()}

    # 同一份隔离工作区反复注入/恢复缺陷：只导入一次 Godot，仍不触碰仓库文件。
    workspace = behavior.BehaviorWorkspace(FEATURES, _godot)
    workspace_features = os.path.join(workspace.project, "Features")

    def verify_in_workspace(feature):
        return behavior.verify_feature(feature, FEATURES, workspace.project, _godot,
                                       replay=1, workspace=workspace)

    def perturb(relative, old, new_text):
        path = os.path.join(workspace_features, relative)
        with open(path, "rb") as handle:
            original = handle.read()
        body = original.decode("utf-8")
        if old not in body:
            raise AssertionError("patch anchor not found in %s" % relative)
        write_text(path, body.replace(old, new_text, 1))
        return path, original

    try:
        path, original = perturb("moving_platform/moving_platform.gd",
                                 "	global_position = _origin + travel * phase",
                                 "	global_position = _origin")
        report = verify_in_workspace("moving_platform")[0]
        ok("case6: a platform that never moves -> MISMATCH (not PASS)",
           report.status == behavior.STATUS_MISMATCH
           and report.reason == "state_mismatch", json.dumps(report.to_dict())[:300])
        restore(path, original)
        ok("case6: frozen-platform copy restored byte-for-byte",
           sha256(path) == baseline["platform"])

        # 缺陷：位移只增不减（不走三角波回程），且不在 4 秒边界回绕
        path, original = perturb("moving_platform/moving_platform.gd",
                                 "	var phase := 1.0 - absf(cycle * 2.0 - 1.0)",
                                 "	var phase := clampf(_time / 2.0, 0.0, 1.0)")
        by_id = {(item.feature, item.behavior): item
                 for item in verify_in_workspace("moving_platform")}
        ok("case6: one-way motion still satisfies travel (the control is specific)",
           by_id[("moving_platform", "travel")].status == behavior.STATUS_PASS,
           json.dumps(by_id[("moving_platform", "travel")].to_dict())[:300])
        ok("case6: a platform that never returns -> round_trip MISMATCH",
           by_id[("moving_platform", "round_trip")].status == behavior.STATUS_MISMATCH,
           json.dumps(by_id[("moving_platform", "round_trip")].to_dict())[:300])
        restore(path, original)

        path, original = perturb("moving_platform/moving_platform.gd",
                                 "@export var period := 4.0",
                                 "@export var period := 400.0")
        report = verify_in_workspace("moving_platform")[0]
        ok("case6: an observation window that never sees the move -> MISMATCH, not PASS",
           report.status == behavior.STATUS_MISMATCH, json.dumps(report.to_dict())[:300])
        restore(path, original)

        path, original = perturb("trigger_switch/trigger_switch.gd",
                                 "\t\t\t_triggered = true\n\t\t\tactivated.emit(true)",
                                 "\t\t\tactivated.emit(true)")
        report = verify_in_workspace("trigger_switch")[0]
        ok("case6: a switch that emits without changing state -> MISMATCH",
           report.status == behavior.STATUS_MISMATCH, json.dumps(report.to_dict())[:300])
        restore(path, original)

        path, original = perturb("trigger_switch/trigger_switch.gd",
                                 "func is_triggered() -> bool:",
                                 "func is_triggered_removed() -> bool:")
        report = verify_in_workspace("trigger_switch")[0]
        ok("case6: an unavailable observation -> INSUFFICIENT, never PASS",
           report.status == behavior.STATUS_INSUFFICIENT,
           json.dumps(report.to_dict())[:300])
        restore(path, original)
    finally:
        workspace.close()

    ok("case6: every repository script is still at its original hash",
       all(sha256(path) == baseline[name] for name, path in scripts.items()))

    # CLI 退出码：真实缺陷 → 非 0（在本次拥有的 Features 副本上注入，随后恢复）
    cli_features = copied_features("cli")
    cli_script = os.path.join(cli_features, "moving_platform", "moving_platform.gd")
    defect = patch(cli_script, "	global_position = _origin + travel * phase",
                   "	global_position = _origin")
    proc = subprocess.run([sys.executable, CLI, "--feature", "moving_platform",
                           "--features-dir", cli_features], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300,
                          stdin=subprocess.DEVNULL, cwd=PROJECT_ROOT)
    ok("case6: the CLI exits non-zero for a real behavior defect",
       proc.returncode == 1 and "MISMATCH" in (proc.stdout or ""),
       "exit=%s out=%s" % (proc.returncode, (proc.stdout or "")[-200:]))
    restore(cli_script, defect)
    ok("case6: the CLI fixture is restored byte-for-byte",
       sha256(cli_script) == baseline["platform"])

    # 协议漂移：隔离副本移除帧推进实现映射 → 能力门禁失败；恢复后通过
    drift = os.path.join(_tempdir, "drift", "project")
    probes = os.path.join(drift, ".ai", "tools", "scene_composer", "probes")
    os.makedirs(probes, exist_ok=True)
    probe_copy = shutil.copyfile(behavior.PROBE_PATH,
                                 os.path.join(probes, "feature_behavior_probe.gd"))
    shutil.copyfile(behavior_protocol.MANIFEST_PATH,
                    os.path.join(probes, "behavior_manifest.json"))
    write_text(os.path.join(drift, "project.godot"),
               "config_version=5\n\n[application]\nconfig/name=\"drift\"\n")
    probe_bytes = open(probe_copy, "rb").read()
    ok("case6: the untouched copy satisfies the capability gate",
       behavior_protocol.check_capabilities(
           protocol, behavior_protocol.probe_capabilities(drift, _godot)) == [])
    write_text(probe_copy, probe_bytes.decode().replace(
        "\t\"simulation_advance_frames\": \"_impl_simulation_advance_frames\",\n", ""))
    errors = behavior_protocol.check_capabilities(
        protocol, behavior_protocol.probe_capabilities(drift, _godot))
    ok("case6: dropping the frame-advance implementation breaks the gate",
       any("simulation_advance_frames" in error for error in errors), str(errors))
    restore(probe_copy, probe_bytes)
    ok("case6: probe copy restored byte-for-byte",
       sha256(probe_copy) == hashlib.sha256(probe_bytes).hexdigest())
    ok("case6: the gate passes again after the restore",
       behavior_protocol.check_capabilities(
           protocol, behavior_protocol.probe_capabilities(drift, _godot)) == [])

    # manifest 漂移：改协议但不重新生成 → 拒绝运行
    drifted_path = os.path.join(_tempdir, "drifted_protocol.yaml")
    with open(behavior_protocol.PROTOCOL_PATH, encoding="utf-8") as handle:
        protocol_text = handle.read()
    write_text(drifted_path, protocol_text.replace("max_total_frames: 600",
                                                   "max_total_frames: 500", 1))
    drifted = behavior_protocol.load_protocol(drifted_path)
    ok("case6: a protocol edit without regenerating the manifest is drift",
       behavior_protocol.check_manifest(drifted) != [])
    report = behavior.verify_feature("moving_platform", FEATURES, FEATURES, _godot,
                                     replay=1, protocol=drifted)[0]
    ok("case6: the verifier refuses to run on a drifted manifest",
       report.status == behavior.STATUS_INVALID and report.reason == "protocol_drift",
       json.dumps(report.to_dict())[:300])

    # ---------------- Case 7: 既有 behavior 语义不变 ----------------
    print("=== Case 7: the Phase 1.40 behaviors keep their semantics ===")
    workspace = behavior.BehaviorWorkspace(FEATURES, _godot)
    observed = {}
    try:
        for feature in ("openable_door", "health", "heal_pickup", "collect_pickup"):
            for report in behavior.verify_feature(feature, FEATURES, FEATURES, _godot,
                                                  replay=1, workspace=workspace):
                observed[(report.feature, report.behavior)] = report
    finally:
        workspace.close()
    # Phase 1.51：health 新增 2 条（过杀下限钳制 / 死后守卫），这四个 Feature 的
    # behavior 总数由 6 变为 8。计数跟随仓库真实声明，不是放宽断言。
    ok("case7: eight behaviors reported for these four legacy Features",
       len(observed) == 8, str(sorted(observed)))
    for key, report in sorted(observed.items()):
        ok("case7: %s/%s still PASS" % key,
           report.status == behavior.STATUS_PASS and report.replay_consistent,
           json.dumps(report.to_dict())[:300])
    damage = observed.get(("health", "damage"))
    if damage:
        values = {check["check"]: check["observed"] for check in damage.actual}
        ok("case7: health.damage still observes 5 -> 1",
           values.get("health.current") == 1, str(values))


if __name__ == "__main__":
    sys.exit(main())
