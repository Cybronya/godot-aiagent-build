#!/usr/bin/env python3
"""Behavior Protocol 一致性测试（Phase 1.41）

协议 `.ai/context/behavior_protocol.yaml` 是动作/观测能力的唯一权威；探针读取由它
生成的 `behavior_manifest.json`。本测试锁定：

    Case 1  协议加载：版本、能力数量、全部 implemented
    Case 2  manifest 与协议逐字一致（生成物未漂移）
    Case 3  探针真实实现映射与协议声明一致（--capabilities 门禁）
    Case 4  协议缺失 / 损坏 / 版本不兼容 / 重复 ID / 未知类型 / 非法引用 → 拒绝
    Case 5  声明但未实现的能力：加载可识别，使用即 INVALID
    Case 6  Python 与 Godot 对未知动作 / 参数 / 检查 / 信号给出兼容拒绝
    Case 7  协议漂移负向对照（隔离副本移除实现映射 / 篡改 manifest 版本）+ 恢复
    Case 8  全部 behavior（含 Phase 1.42 时间驱动 6 个）双次重放一致
    Case 9  行为负向对照（no-op 动作）仍 MISMATCH，副本哈希恢复
    Case 10 Phase 1.38 静态对账与 Phase 1.39 运行时证据继续 PASS

Phase 1.42：协议升到 v2（limits / fixture / advances_frames / properties / enum / float
类型），本测锁定 v2 结构与新增能力的声明−实现一致。

用法:
    python .ai/tools/scene_composer/tests/test_behavior_protocol_consistency.py
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
TOOL_DIR = os.path.dirname(_HERE)
TOOLS_DIR = os.path.dirname(TOOL_DIR)
DOTAI = os.path.dirname(TOOLS_DIR)
PROJECT_ROOT = os.path.dirname(DOTAI)
FEATURES = os.path.join(PROJECT_ROOT, "Features")

for path in (TOOL_DIR, TOOLS_DIR, _HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import behavior_protocol                                          # noqa: E402
import feature_behavior_evidence as behavior                      # noqa: E402
import instance_evidence                                          # noqa: E402
import runtime_instance_evidence as runtime_evidence              # noqa: E402

_failures = []

MINIMAL_PROTOCOL = """protocol_version: 2
status: current
targets:
  kinds:
    node: "scene node"
limits:
  max_frames_per_action: 300
  max_total_frames: 600
  max_fixture_actions: 4
actions:
  demo.act:
    implementation: demo_act
    implemented: true
    target: node
    params: {}
observations:
  demo.state:
    implementation: observe_demo_state
    implemented: true
    target: node
    result: {type: bool}
    params:
      equals: {type: bool, required: true}
signals:
  demo.changed:
    signal: changed
    args: [bool]
properties:
  demo.mode:
    property: mode
    class: DemoNode
    values: [A, B]
"""


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


def read_text(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expect_protocol_error(name: str, text: str, needle: str = "") -> None:
    path = os.path.join(tempdir, "protocols", name + ".yaml")
    write_text(path, text)
    try:
        behavior_protocol.load_protocol(path)
        ok("case4: %s is rejected" % name, False, "protocol loaded unexpectedly")
    except behavior_protocol.ProtocolError as exc:
        ok("case4: %s is rejected" % name, needle in str(exc) if needle else True, str(exc))


def project_with_probe(root: str, features: bool = False) -> str:
    project = os.path.join(root, "project")
    os.makedirs(project, exist_ok=True)
    probes = os.path.join(project, ".ai", "tools", "scene_composer", "probes")
    os.makedirs(probes, exist_ok=True)
    shutil.copyfile(behavior.PROBE_PATH, os.path.join(probes, "feature_behavior_probe.gd"))
    shutil.copyfile(behavior_protocol.MANIFEST_PATH,
                    os.path.join(probes, "behavior_manifest.json"))
    if features:
        shutil.copytree(FEATURES, os.path.join(project, "Features"))
    write_text(os.path.join(project, "project.godot"),
               "config_version=5\n\n[application]\nconfig/name=\"protocol-gate\"\n")
    return project


def probe_contract(project: str, contract: dict, godot: str) -> dict:
    observation = behavior.run_probe(contract, project, godot, timeout_s=60)
    return observation.get("result") or {}


def main() -> int:
    global tempdir
    godot = runtime_evidence.find_godot(PROJECT_ROOT)
    if not godot:
        print("SKIP: godot executable not found; protocol gate cannot be verified")
        return 1
    tempdir = tempfile.mkdtemp(prefix="protocol_tests_", dir=os.path.join(DOTAI, "tmp"))
    try:
        # ---------------- Case 1/2: 协议与 manifest ----------------
        print("=== Case 1: the protocol is the single capability definition ===")
        protocol = behavior_protocol.load_protocol()
        ok("case1: protocol_version is 2",
           protocol.version == behavior_protocol.SUPPORTED_PROTOCOL_VERSION == 2,
           str(protocol.version))
        # Phase 1.46 追加 gate.is_fulfilled 观测与 gate.fulfilled 信号（组合场景链所需）；
        # Phase 1.49 追加 stun.stunned 信号（眩晕状态跨越广播）；
        # Phase 1.50 追加 health_bar.ratio 观测（血条的只读显示状态，动作表未变）。
        # Phase 1.52 追加 cooldown.start / screenshake.add_trauma 动作、
        # cooldown.is_ready 观测与 6 个组件状态信号登记（code_library 批量资产）。
        # 计数仍然精确锁定，不允许静默增减能力。
        ok("case1: ten actions / thirteen observations / thirteen signals / one property",
           (len(protocol.actions), len(protocol.observations), len(protocol.signals),
            len(protocol.properties)) == (10, 13, 13, 1),
           str((len(protocol.actions), len(protocol.observations), len(protocol.signals),
                len(protocol.properties))))
        ok("case1: every entry is explicitly implemented",
           all(spec["implemented"] for spec in protocol.actions.values())
           and all(spec["implemented"] for spec in protocol.observations.values()))
        ok("case1: implementations are unique per capability",
           len({spec["implementation"] for spec in protocol.actions.values()}) == 10
           and len({spec["implementation"] for spec in protocol.observations.values()}) == 13)
        ok("case1: limits and fixture/advance flags are declared",
           protocol.limits == {"max_frames_per_action": 300, "max_total_frames": 600,
                               "max_fixture_actions": 4},
           str(protocol.limits))
        advancing = [name for name, spec in protocol.actions.items() if spec["advances_frames"]]
        fixtures = [name for name, spec in protocol.actions.items() if spec["fixture"]]
        ok("case1: exactly one frame-advancing action and one fixture action",
           advancing == ["simulation.advance_frames"] and fixtures == ["state.set_property"],
           "%s / %s" % (advancing, fixtures))
        frames_param = protocol.action("simulation.advance_frames")["params"]["frames"]
        ok("case1: the frames param max equals limits.max_frames_per_action",
           frames_param["max"] == protocol.limits["max_frames_per_action"],
           str(frames_param))
        ok("case1: the frame phase only allows physics",
           protocol.action("simulation.advance_frames")["params"]["phase"]["values"]
           == ["physics"])

        print("=== Case 2: the generated manifest matches the protocol ===")
        ok("case2: manifest has no drift", behavior_protocol.check_manifest(protocol) == [],
           str(behavior_protocol.check_manifest(protocol)))
        manifest_text = read_text(behavior_protocol.MANIFEST_PATH)
        manifest = json.loads(manifest_text)
        ok("case2: manifest is generated JSON without prose",
           manifest.get("protocol_version") == 2 and "summary" not in manifest_text)
        ok("case2: manifest carries limits, fixture flags and properties",
           manifest.get("limits") == protocol.limits
           and manifest["actions"]["state.set_property"]["fixture"] is True
           and manifest["actions"]["simulation.advance_frames"]["advances_frames"] is True
           and manifest.get("properties") == protocol.properties)
        generated = protocol.manifest_text()
        ok("case2: regenerating is byte-identical", generated == manifest_text)

        # ---------------- Case 3: 探针实现映射 ----------------
        print("=== Case 3: probe implementations match the protocol ===")
        capabilities = behavior_protocol.probe_capabilities(PROJECT_ROOT, godot)
        ok("case3: probe reports protocol_version 2",
           capabilities.get("protocol_version") == 2, str(capabilities)[:200])
        ok("case3: probe manifest is valid", not capabilities.get("manifest_error"),
           str(capabilities.get("manifest_error")))
        ok("case3: no missing or undeclared implementations",
           behavior_protocol.check_capabilities(protocol, capabilities) == [],
           str(behavior_protocol.check_capabilities(protocol, capabilities)))
        ok("case3: probe implements exactly the declared actions",
           sorted(capabilities.get("actions") or []) == protocol.required_implementations()["actions"])
        ok("case3: probe implementation map covers the time-driven capabilities",
           all(name in (capabilities.get("actions") or []) for name in
               ("simulation_advance_frames", "state_set_property", "input_press",
                "input_release"))
           and all(name in (capabilities.get("observations") or []) for name in
                   ("observe_node2d_position", "observe_node2d_displacement",
                    "observe_trigger_is_triggered", "observe_node_exists")))

        # ---------------- Case 4: 协议非法输入 ----------------
        print("=== Case 4: invalid protocols are rejected, never downgraded ===")
        expect_protocol_error("empty", "", "non-empty")
        try:
            behavior_protocol.load_protocol(os.path.join(tempdir, "nope.yaml"))
            ok("case4: missing protocol file is rejected", False)
        except behavior_protocol.ProtocolError as exc:
            ok("case4: missing protocol file is rejected", "not found" in str(exc), str(exc))
        expect_protocol_error("corrupt", "protocol_version: [unclosed\n", "")
        expect_protocol_error("version", MINIMAL_PROTOCOL.replace(
            "protocol_version: 2", "protocol_version: 3"), "incompatible")
        expect_protocol_error("no_limits", MINIMAL_PROTOCOL.replace(
            "limits:\n  max_frames_per_action: 300\n  max_total_frames: 600\n"
            "  max_fixture_actions: 4\n", ""), "limits")
        expect_protocol_error("bad_limit", MINIMAL_PROTOCOL.replace(
            "max_fixture_actions: 4", "max_fixture_actions: 0"), "positive integer")
        expect_protocol_error("limit_order", MINIMAL_PROTOCOL.replace(
            "max_frames_per_action: 300", "max_frames_per_action: 900"), "must not exceed")
        expect_protocol_error("advance_without_frames", MINIMAL_PROTOCOL.replace(
            "    target: node\n    params: {}",
            "    target: node\n    advances_frames: true\n    params: {}"),
            "requires a required int param 'frames'")
        expect_protocol_error("frames_over_limit", MINIMAL_PROTOCOL.replace(
            "    target: node\n    params: {}",
            "    target: node\n    advances_frames: true\n"
            "    params:\n      frames: {type: int, required: true, min: 1, max: 700}"),
            "max_frames_per_action")
        expect_protocol_error("enum_without_values", MINIMAL_PROTOCOL.replace(
            "      equals: {type: bool, required: true}",
            "      mode: {type: enum, required: true}"), "enum requires values")
        expect_protocol_error("enum_duplicate_values", MINIMAL_PROTOCOL.replace(
            "      equals: {type: bool, required: true}",
            "      mode: {type: enum, required: true, values: [A, A]}"), "duplicates")
        expect_protocol_error("property_bad_values", MINIMAL_PROTOCOL.replace(
            "    values: [A, B]", "    values: []"), "non-empty list of strings")
        expect_protocol_error("property_bad_class", MINIMAL_PROTOCOL.replace(
            "    class: DemoNode", "    class: 7Demo"), "global class name")
        expect_protocol_error("property_ref_without_value", MINIMAL_PROTOCOL.replace(
            "    target: node\n    params: {}",
            "    target: node\n    params:\n"
            "      property: {type: property_ref, required: true}"),
            "no 'value' parameter")
        expect_protocol_error("duplicate", MINIMAL_PROTOCOL.replace(
            "  demo.act:\n", "  demo.act: {implementation: demo_act, implemented: true, "
                             "target: node}\n  demo.act:\n"), "duplicate")
        expect_protocol_error("bad_type", MINIMAL_PROTOCOL.replace(
            "equals: {type: bool, required: true}",
            "equals: {type: decimal, required: true}"), "unknown type")
        expect_protocol_error("bad_target", MINIMAL_PROTOCOL.replace(
            "target: node", "target: spaceship"), "target kind")
        expect_protocol_error("unknown_key", MINIMAL_PROTOCOL.replace(
            "    implemented: true\n", "    implemented: true\n    magic: true\n", 1),
            "unknown keys")
        expect_protocol_error("not_bool", MINIMAL_PROTOCOL.replace(
            "    implemented: true\n", "    implemented: 1\n", 1), "implemented must be a bool")

        # ---------------- Case 5: 声明但未实现 ----------------
        print("=== Case 5: declared-but-unimplemented capabilities are never usable ===")
        not_impl_path = os.path.join(tempdir, "protocols", "not_impl.yaml")
        write_text(not_impl_path, MINIMAL_PROTOCOL.replace(
            "  demo.act:\n    implementation: demo_act\n    implemented: true",
            "  demo.act:\n    implementation: demo_act\n    implemented: false"))
        pending = behavior_protocol.load_protocol(not_impl_path)
        action, errors = pending.validate_action({"type": "demo.act", "params": {}}, 0)
        ok("case5: protocol loads with an explicit unimplemented entry",
           pending.version == 2 and action is None)
        ok("case5: using it is INVALID with a clear reason",
           errors and "declared but not implemented" in errors[0], str(errors))
        ok("case5: the requirement map excludes unimplemented entries",
           pending.required_implementations()["actions"] == [],
           str(pending.required_implementations()))

        features = os.path.join(tempdir, "features_pending", "Features")
        directory = os.path.join(features, "pending")
        os.makedirs(directory, exist_ok=True)
        write_text(os.path.join(directory, "template.yaml"),
                   "feature:\n  id: pending\nscene:\n  source: Pending.tscn\n"
                   "behavior:\n  - id: a\n    actions: [{type: demo.act}]\n"
                   "    expected: [{check: demo.state, target: \".\", equals: true}]\n")
        report = behavior.verify_feature("pending", features, FEATURES, "", replay=1,
                                         protocol=pending, manifest_path=None)[0]
        ok("case5: verifier returns INVALID without launching Godot",
           report.status == behavior.STATUS_INVALID and report.reason == "contract_invalid"
           and "not implemented" in report.detail, report.detail)

        # 缺少协议 / 损坏协议 → 验证器 INVALID，不是宽松模式
        for name, text in (("missing", None), ("corrupt", "protocol_version: [\n")):
            path = os.path.join(tempdir, "protocols", "verifier_%s.yaml" % name)
            if text is not None:
                write_text(path, text)
            report = behavior.verify_feature("openable_door", FEATURES, FEATURES, "",
                                             replay=1, protocol_path=path)[0]
            ok("case5: verifier fails closed on %s protocol" % name,
               report.status == behavior.STATUS_INVALID
               and report.reason == "protocol_invalid", str(report.to_dict())[:200])

        # manifest 漂移也必须 fail closed
        drifted_protocol_path = os.path.join(tempdir, "protocols", "drifted.yaml")
        write_text(drifted_protocol_path, read_text(behavior_protocol.PROTOCOL_PATH).replace(
            "        max: 100\n", "        max: 99\n", 1))
        drifted = behavior_protocol.load_protocol(drifted_protocol_path)
        ok("case5: a changed protocol is detected as manifest drift",
           behavior_protocol.check_manifest(drifted) != [])
        report = behavior.verify_feature("openable_door", FEATURES, FEATURES, "",
                                         replay=1, protocol=drifted)[0]
        ok("case5: verifier refuses to run with a drifted manifest",
           report.status == behavior.STATUS_INVALID and report.reason == "protocol_drift",
           str(report.to_dict())[:200])

        # ---------------- Case 6: Python / Godot 拒绝一致 ----------------
        print("=== Case 6: Python and Godot reject the same invalid contracts ===")
        project = project_with_probe(tempdir, features=True)
        try:
            subprocess.run([godot, "--headless", "--path", project, "--import"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired):
            pass
        base_contract = {
            "feature": "openable_door", "behavior": "parity", "run_id": "parity-run",
            "replay_index": 1, "window_frames": 5,
            "scene": "res://Features/openable_door/OpenableDoor.tscn",
            "preconditions": [],
            "expected": [{"check": "door.is_open", "target": ".", "equals": True}],
        }
        invalid_cases = {
            "unknown_action": {
                "actions": [{"type": "door.force_open", "params": {}}]},
            "wrong_param_type": {
                "actions": [{"type": "door.set_open", "params": {"value": 1}}]},
            "unknown_check": {
                "actions": [{"type": "door.set_open", "params": {"value": True}}],
                "expected": [{"check": "door.is_shiny", "target": ".", "equals": True}]},
            "unknown_signal": {
                "actions": [{"type": "door.set_open", "params": {"value": True}}],
                "expected": [{"check": "signal", "entry": "door.teleported", "count": 1}]},
        }
        for name, override in invalid_cases.items():
            contract = dict(base_contract)
            contract.update(override)
            contract["run_id"] = "parity-%s" % name
            python_errors = []
            python_errors.extend(behavior_protocol.load_protocol().validate_action(
                contract["actions"][0], 0)[1])
            for index, entry in enumerate(contract["expected"]):
                python_errors.extend(behavior_protocol.load_protocol().validate_check(
                    entry, index, "expected")[1])
            payload = probe_contract(project, contract, godot)
            ok("case6: %s rejected by Python" % name, bool(python_errors), str(python_errors))
            ok("case6: %s rejected by Godot as INVALID/contract_invalid" % name,
               payload.get("status") == "INVALID" and payload.get("reason") == "contract_invalid",
               json.dumps(payload)[:300])
            ok("case6: %s never becomes PASS" % name, payload.get("status") != "PASS")

        # ---------------- Case 7: 真实协议漂移负向对照 ----------------
        print("=== Case 7: real protocol drift is caught and recovery is verified ===")
        drift_project = project_with_probe(os.path.join(tempdir, "drift"), features=False)
        probe_copy = os.path.join(drift_project, ".ai", "tools", "scene_composer", "probes",
                                  "feature_behavior_probe.gd")
        manifest_copy = os.path.join(os.path.dirname(probe_copy), "behavior_manifest.json")
        probe_bytes = open(probe_copy, "rb").read()
        manifest_bytes = open(manifest_copy, "rb").read()

        def restore(path: str, payload: bytes) -> None:
            with open(path, "wb") as handle:
                handle.write(payload)
        baseline = {
            probe_copy: sha256(probe_copy),
            manifest_copy: sha256(manifest_copy),
            os.path.join(FEATURES, "openable_door", "openable_door.gd"):
                sha256(os.path.join(FEATURES, "openable_door", "openable_door.gd")),
        }
        ok("case7: the untouched copy matches the protocol",
           behavior_protocol.check_capabilities(
               protocol, behavior_protocol.probe_capabilities(drift_project, godot)) == [])

        write_text(probe_copy, probe_bytes.decode().replace(
            "\t\"door_set_open\": \"_impl_door_set_open\",\n", ""))
        drifted_caps = behavior_protocol.probe_capabilities(drift_project, godot)
        drift_errors = behavior_protocol.check_capabilities(protocol, drifted_caps)
        ok("case7: removing an implementation mapping breaks the gate",
           any("door_set_open" in error for error in drift_errors), str(drift_errors))
        restore(probe_copy, probe_bytes)
        ok("case7: probe copy restored byte-for-byte",
           sha256(probe_copy) == baseline[probe_copy])
        ok("case7: recovery passes the gate again",
           behavior_protocol.check_capabilities(
               protocol, behavior_protocol.probe_capabilities(drift_project, godot)) == [])

        # manifest 版本漂移：探针读取即拒绝，恢复后重新 PASS
        write_text(manifest_copy, manifest_bytes.decode().replace(
            "\"protocol_version\": 2", "\"protocol_version\": 99"))
        bad = probe_contract(drift_project, {
            "feature": "openable_door", "behavior": "manifest", "run_id": "manifest-drift",
            "replay_index": 1, "window_frames": 5,
            "scene": "res://Features/openable_door/OpenableDoor.tscn",
            "actions": [{"type": "door.set_open", "params": {"value": True}}],
            "preconditions": [], "expected": [{"check": "door.is_open", "target": ".",
                                               "equals": True}],
        }, godot)
        ok("case7: an incompatible manifest cannot execute the probe",
           bad.get("status") == "INVALID" and bad.get("reason") == "protocol_invalid",
           json.dumps(bad)[:300])
        restore(manifest_copy, manifest_bytes)
        ok("case7: manifest copy restored byte-for-byte",
           sha256(manifest_copy) == baseline[manifest_copy])
        ok("case7: repository probe/manifest/Feature are untouched",
           all(sha256(path) == digest for path, digest in baseline.items()))

        # ---------------- Case 8/9: 现有 behavior 与负向对照 ----------------
        print("=== Case 8: every declared behavior still passes with two replays ===")
        workspace = behavior.BehaviorWorkspace(FEATURES, godot)
        reports = []
        try:
            for feature in behavior.declared_features():
                reports.extend(behavior.verify_feature(
                    feature, FEATURES, FEATURES, godot, replay=2, workspace=workspace,
                    protocol=protocol))
        finally:
            workspace.close()
        ok("case8: forty-nine behaviors checked", len(reports) == 49, str(len(reports)))
        checked = {(report.feature, report.behavior) for report in reports}
        ok("case8: the six Phase 1.40 behaviors are still declared",
           checked.issuperset({
               ("openable_door", "open"), ("health", "damage"),
               ("health", "heal_clamped"), ("health", "death"),
               ("heal_pickup", "heal_damaged_target"),
               ("collect_pickup", "collect_on_contact")}), str(sorted(checked)))
        ok("case8: the Phase 1.42 time-driven behaviors are still declared",
           checked.issuperset({
               ("moving_platform", "travel"), ("moving_platform", "round_trip"),
               ("trigger_switch", "latch_once"),
               ("trigger_switch", "toggle_on_second_contact"),
               ("player_movement", "move_right"),
               ("player_movement", "stop_on_release")}), str(sorted(checked)))
        ok("case8: the Phase 1.43 chase behaviors are declared",
           checked.issuperset({("chase_movement", "approach_target"),
                               ("chase_movement", "hold_without_target")}),
           str(sorted(checked)))
        ok("case8: the Phase 1.44 condition_gate behaviors are declared",
           checked.issuperset({("condition_gate", "partial_conditions_block_output"),
                               ("condition_gate", "all_conditions_fulfill"),
                               ("condition_gate", "condition_fallback_withdraws_output")}),
           str(sorted(checked)))
        ok("case8: the Phase 1.47 contact_damage behaviors are declared",
           checked.issuperset({("contact_damage", "damage_on_contact"),
                               ("contact_damage", "no_damage_without_contact"),
                               ("contact_damage", "damage_amount_is_respected")}),
           str(sorted(checked)))
        ok("case8: the Phase 1.49 stun behaviors are declared",
           checked.issuperset({("stun", "hit_stuns_and_freezes_host"),
                               ("stun", "stun_expires_and_host_resumes"),
                               ("stun", "heal_does_not_stun"),
                               ("stun", "death_guard_rejects_stun"),
                               ("stun", "reentry_extends_without_rebroadcast")}),
           str(sorted(checked)))
        ok("case8: the Phase 1.50 health_bar behaviors are declared",
           checked.issuperset({
               ("health_bar", "initial_health_bar_ratio"),
               ("health_bar", "damage_updates_health_bar"),
               ("health_bar", "healing_updates_health_bar"),
               ("health_bar", "death_empties_health_bar"),
               ("health_bar", "unbound_bar_reports_no_fill")}),
           str(sorted(checked)))
        # Phase 1.51：health 补上过杀下限钳制与死后守卫（原本 3 条契约看不见的两个缺陷）。
        ok("case8: the Phase 1.51 health behaviors are declared",
           checked.issuperset({("health", "overkill_clamps_at_zero"),
                               ("health", "post_death_guard")}),
           str(sorted(checked)))
        for report in reports:
            ok("case8: %s/%s PASS with consistent replays" % (report.feature, report.behavior),
               report.status == behavior.STATUS_PASS and report.replay_count == 2
               and report.replay_consistent, json.dumps(report.to_dict())[:400])

        print("=== Case 9: a real behavior defect is still detected ===")
        features = os.path.join(tempdir, "features_negative", "Features")
        shutil.copytree(FEATURES, features)
        script = os.path.join(features, "openable_door", "openable_door.gd")
        original = open(script, "rb").read()
        write_text(script, original.decode().replace(
            "func set_open(value: bool) -> void:\n"
            "\tif _is_open == value:\n\t\treturn\n\t_apply(value)\n",
            "func set_open(value: bool) -> void:\n\tpass\n"))
        report = behavior.verify_feature("openable_door", features, FEATURES, godot,
                                         replay=1, protocol=protocol)[0]
        ok("case9: no-op action -> MISMATCH / state_mismatch",
           report.status == behavior.STATUS_MISMATCH and report.reason == "state_mismatch",
           str(report.to_dict())[:300])
        with open(script, "wb") as handle:
            handle.write(original)
        ok("case9: fixture script restored byte-for-byte",
           sha256(script) == hashlib.sha256(original).hexdigest())

        # ---------------- Case 10: 1.38 / 1.39 回归 ----------------
        print("=== Case 10: static and runtime instance evidence still pass ===")
        for feature in instance_evidence.declared_features():
            ok("case10: %s static reconciliation PASS" % feature,
               instance_evidence.reconcile_feature(feature).status
               == instance_evidence.STATUS_PASS)
        for feature in runtime_evidence.declared_features():
            report = runtime_evidence.verify_feature(feature, godot=godot)
            ok("case10: %s runtime instance PASS" % feature,
               report.status == runtime_evidence.STATUS_PASS, report.detail)
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all behavior protocol consistency checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
