#!/usr/bin/env python3
"""条件门控行为证据测试（Phase 1.44）

Phase 1.42 的协议 v2 与 Phase 1.43 的 `behavior[].scene` 已能表达「真实物理接触 →
组件状态 → 下游动作」的链路，因此 `condition_gate` 不需要新增任何协议能力：

    Case 1  正向证据：partial / all / fallback 三条行为全部 PASS，2/2 重放一致
    Case 2  真实缺陷：忽略 condition_count / 断开条件输入 / 阻断输出信号 → MISMATCH
            （且互不影响，未涉及的 behavior 仍 PASS）
    Case 3  条件永不满足：观察窗口耗尽 → MISMATCH，绝不 PASS
    Case 4  观测不可用：目标节点缺失 → INSUFFICIENT（precondition_unmet / check_unavailable）
    Case 5  契约边界：跨 Feature 夹具被拒绝；动作 / 观测仍在协议 v2 之内
    Case 6  CLI 对真实缺陷返回 1、对仓库 Feature 返回 0；副本按 SHA256 恢复

`condition_gate` 的入口场景只有一个 Node 根（没有条件源、没有下游），无法区分
「门控未达成」与「门控逻辑失效」，因此三条 behavior 都使用同目录的
`ConditionGateFixture.tscn`：Gate(condition_count=2, All) + SwitchA(Latching) +
SwitchB(Toggle) + Door，连接方式与 feature.yaml 的 composition 契约一致。
`scene` 只选择证据场景，不增加动作、观测或写入能力。

用法:
    python .ai/tools/scene_composer/tests/test_condition_gate_behavior.py
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

FEATURE = "condition_gate"
FIXTURE_SCENE = "res://Features/condition_gate/ConditionGateFixture.tscn"
ENTRY_SCENE = "res://Features/condition_gate/ConditionGate.tscn"
BEHAVIORS = ("partial_conditions_block_output", "all_conditions_fulfill",
             "condition_fallback_withdraws_output")


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


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def sha256(path: str) -> str:
    return hashlib.sha256(read_bytes(path)).hexdigest()


def observed(report, check: str, target: str = None, index: int = 0):
    values = [entry.get("observed") for entry in report.actual
              if entry.get("check") == check
              and (target is None or entry.get("target") == target)]
    return values[index] if index < len(values) else None


def probe(actions, expected, scene=FIXTURE_SCENE, window_frames=10,
          preconditions=None, behavior_id="case", tag="", project=""):
    contract = {"feature": FEATURE, "behavior": behavior_id,
                "run_id": "condition-%s-%s" % (behavior_id, tag or behavior_id),
                "replay_index": 1, "window_frames": window_frames, "scene": scene,
                "actions": actions, "preconditions": preconditions or [],
                "expected": expected}
    observation = behavior.run_probe(contract, project or PROJECT_ROOT, _godot,
                                     timeout_s=60)
    return observation.get("result") or {}


def advance(frames):
    return {"type": "simulation.advance_frames", "params": {"frames": frames}}


def overlap(target):
    return {"type": "physics.overlap", "target": target, "params": {"group": "players"}}


def build_feature(name: str, behavior_block, files=None):
    """临时 Features 目录：写入 template.yaml（与可选场景）后跑 Python 契约校验。"""
    features = os.path.join(_tempdir, "contracts")
    directory = os.path.join(features, name)
    body = yaml.safe_dump(behavior_block, allow_unicode=True, sort_keys=False)
    write_text(os.path.join(directory, "template.yaml"),
               "feature:\n  id: %s\nscene:\n  source: Probe.tscn\nbehavior:\n%s"
               % (name, textwrap.indent(body, "  ")))
    for relative, text in (files or {}).items():
        write_text(os.path.join(directory, relative), text)
    return behavior.build_contracts(name, features)


def main() -> int:
    global _godot, _tempdir
    _godot = runtime_evidence.find_godot(PROJECT_ROOT)
    if not _godot:
        print("SKIP: godot executable not found; condition_gate behavior cannot be verified")
        return 1
    os.makedirs(os.path.join(DOTAI, "tmp"), exist_ok=True)
    _tempdir = tempfile.mkdtemp(prefix="condition_gate_behavior_",
                                dir=os.path.join(DOTAI, "tmp"))
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
    print("PASS: all condition_gate behavior checks passed")
    return 0


def run_cases() -> None:
    protocol = behavior_protocol.load_protocol()

    # ---------------- Case 1: 真实证据 + 重放 ----------------
    print("=== Case 1: condition_gate gates on real switch contacts ===")
    workspace = behavior.BehaviorWorkspace(FEATURES, _godot)
    try:
        reports = behavior.verify_feature(FEATURE, FEATURES, FEATURES, _godot,
                                          replay=2, workspace=workspace)
        by_id = {report.behavior: report for report in reports}
        ok("case1: three behaviors were checked", set(by_id) == set(BEHAVIORS),
           str(sorted(by_id)))
        for name in BEHAVIORS:
            report = by_id.get(name)
            ok("case1: %s PASS with two consistent replays" % name,
               report is not None and report.status == behavior.STATUS_PASS
               and report.replay_count == 2 and report.replay_consistent,
               json.dumps(report.to_dict(), ensure_ascii=False)[:400] if report else "missing")
            ok("case1: %s executed the real actions" % name,
               report is not None and report.action_executed
               and all(entry.get("executed") is True
                       for entry in report.runs[0].get("actions") or [])
               and len(report.runs[0].get("actions") or []) >= 2)
            ok("case1: %s keeps evidence paths" % name,
               report is not None and all(run.get("artifacts", {}).get("contract")
                                          for run in report.runs))

        partial = by_id.get("partial_conditions_block_output")
        if partial:
            ok("case1: one of two conditions leaves the output blocked",
               observed(partial, "door.is_open") is False
               and observed(partial, "trigger.is_triggered", "SwitchA") is True
               and observed(partial, "trigger.is_triggered", "SwitchB") is False,
               json.dumps([entry.get("observed") for entry in partial.actual]))
            ok("case1: the blocked case still proves the input was delivered",
               observed(partial, "signal") == 0
               and observed(partial, "trigger.is_triggered", "SwitchA") is True,
               json.dumps([entry.get("observed") for entry in partial.actual]))

        full = by_id.get("all_conditions_fulfill")
        if full:
            ok("case1: both conditions drive the output exactly once",
               observed(full, "door.is_open") is True
               and observed(full, "signal") == 1
               and observed(full, "trigger.is_triggered", "SwitchA") is True
               and observed(full, "trigger.is_triggered", "SwitchB") is True,
               json.dumps([entry.get("observed") for entry in full.actual]))
            ok("case1: the single output transition carries the fulfilled value",
               [entry.get("observed") for entry in full.actual
                if entry.get("check") == "signal"] == [1]
               and all(run.get("status") == behavior.STATUS_PASS
                       for run in full.runs))

        fallback = by_id.get("condition_fallback_withdraws_output")
        if fallback:
            ok("case1: a falling condition withdraws the output",
               observed(fallback, "door.is_open") is False
               and observed(fallback, "trigger.is_triggered", "SwitchB") is False
               and observed(fallback, "signal") == 2,
               json.dumps([entry.get("observed") for entry in fallback.actual]))
            ok("case1: the fallback case is distinguished by event count, not final state",
               observed(fallback, "signal") == 2
               and observed(partial, "signal") == 0,
               "%s vs %s" % (observed(fallback, "signal"), observed(partial, "signal")))

        contracts, contract_reports = behavior.build_contracts(FEATURE, FEATURES)
        ok("case1: all three behaviors use the Feature-owned fixture scene",
           [contract["scene"] for contract in contracts] == [FIXTURE_SCENE] * 3
           and contract_reports == [],
           str([contract["scene"] for contract in contracts]))
        ok("case1: every contract declares preconditions, expectations and a window",
           all(contract["preconditions"] and contract["expected"]
               and contract["window_frames"] >= 1 for contract in contracts))
        ok("case1: every contract stays inside the frame budget",
           all(protocol.frame_budget_errors(contract["actions"],
                                            contract["window_frames"]) == []
               for contract in contracts))

        used_actions = {action["type"] for contract in contracts
                        for action in contract["actions"]}
        used_checks = {entry["check"] for contract in contracts
                       for entry in contract["preconditions"] + contract["expected"]}
        protocol_actions = set(behavior_protocol.load_protocol().actions)
        protocol_observations = set(behavior_protocol.load_protocol().observations)
        ok("case1: only protocol v2 actions are used",
           used_actions.issubset(protocol_actions), str(sorted(used_actions)))
        ok("case1: only protocol v2 observations are used",
           used_checks.issubset(protocol_observations), str(sorted(used_checks)))

        # ---------------- Case 2: 真实缺陷 ----------------
        print("=== Case 2: real defects produce MISMATCH, not PASS ===")
        workspace_features = os.path.join(workspace.project, "Features")
        script = os.path.join(workspace_features, FEATURE, "condition_gate.gd")
        fixture = os.path.join(workspace_features, FEATURE, "ConditionGateFixture.tscn")
        script_original = read_bytes(script)
        fixture_original = read_bytes(fixture)
        baseline = {
            "script": sha256(os.path.join(FEATURES, FEATURE, "condition_gate.gd")),
            "fixture": sha256(os.path.join(FEATURES, FEATURE, "ConditionGateFixture.tscn")),
            "template": sha256(os.path.join(FEATURES, FEATURE, "template.yaml")),
        }

        def verify_in_workspace():
            return {report.behavior: report
                    for report in behavior.verify_feature(
                        FEATURE, FEATURES, workspace.project, _godot,
                        replay=1, workspace=workspace)}

        def patch(path, old, new):
            text = read_bytes(path).decode("utf-8")
            if old not in text:
                raise AssertionError("patch anchor not found in %s" % path)
            write_text(path, text.replace(old, new, 1))

        # 缺陷 1：All 聚合忽略 condition_count（只有一个条件也判为达成）
        patch(script,
              "\t\tif condition_count > _states.size():\n\t\t\tmet = false\n", "")
        reports = verify_in_workspace()
        ok("case2: ignoring condition_count -> partial case MISMATCH / state_mismatch",
           reports["partial_conditions_block_output"].status == behavior.STATUS_MISMATCH
           and reports["partial_conditions_block_output"].reason == "state_mismatch",
           json.dumps(reports["partial_conditions_block_output"].to_dict())[:300])
        ok("case2: the full-condition case still passes while the threshold is broken",
           reports["all_conditions_fulfill"].status == behavior.STATUS_PASS,
           json.dumps(reports["all_conditions_fulfill"].to_dict())[:300])
        write_text(script, script_original.decode("utf-8"))
        ok("case2: the threshold-defect script is restored byte-for-byte",
           sha256(script) == baseline["script"])

        # 缺陷 2：第二个条件源没有接到门（场景组合断开）
        patch(fixture,
              '[connection signal="activated" from="SwitchB" to="Gate" '
              'method="set_condition" binds=["b"]]\n', "")
        reports = verify_in_workspace()
        ok("case2: a severed condition input -> full case MISMATCH",
           reports["all_conditions_fulfill"].status == behavior.STATUS_MISMATCH,
           json.dumps(reports["all_conditions_fulfill"].to_dict())[:300])
        ok("case2: the partial case still passes while one input is severed",
           reports["partial_conditions_block_output"].status == behavior.STATUS_PASS,
           json.dumps(reports["partial_conditions_block_output"].to_dict())[:300])
        write_text(fixture, fixture_original.decode("utf-8"))
        ok("case2: the severed fixture is restored byte-for-byte",
           sha256(fixture) == baseline["fixture"])

        # 缺陷 3：聚合结果算对了，但门控输出信号不再广播
        patch(script, "\tif met != _is_fulfilled:\n",
              "\tif met != _is_fulfilled and false:\n")
        reports = verify_in_workspace()
        ok("case2: a blocked output signal -> full case MISMATCH",
           reports["all_conditions_fulfill"].status == behavior.STATUS_MISMATCH,
           json.dumps(reports["all_conditions_fulfill"].to_dict())[:300])
        ok("case2: a blocked output signal -> fallback case MISMATCH",
           reports["condition_fallback_withdraws_output"].status == behavior.STATUS_MISMATCH,
           json.dumps(reports["condition_fallback_withdraws_output"].to_dict())[:300])
        ok("case2: the no-output case cannot be hidden by the blocked block",
           reports["partial_conditions_block_output"].status == behavior.STATUS_PASS,
           json.dumps(reports["partial_conditions_block_output"].to_dict())[:300])
        write_text(script, script_original.decode("utf-8"))
        ok("case2: the blocked-signal script is restored byte-for-byte",
           sha256(script) == baseline["script"])

        # ---------------- Case 3: 条件永不满足 ----------------
        print("=== Case 3: a condition that never arrives cannot PASS ===")
        patch(fixture, '[node name="SwitchB" parent="." instance=ExtResource("2_switch")]\n'
                       'position = Vector2(100, 0)\ntrigger_mode = 2\n',
              '[node name="SwitchB" parent="." instance=ExtResource("2_switch")]\n'
              'position = Vector2(100, 0)\ntrigger_mode = 2\ntarget_group = "enemies"\n')
        reports = verify_in_workspace()
        full = reports["all_conditions_fulfill"]
        ok("case3: an unreachable condition source -> MISMATCH, never PASS",
           full.status == behavior.STATUS_MISMATCH
           and full.action_executed is True, json.dumps(full.to_dict())[:300])
        ok("case3: the exhausted window reports the missing input, not success",
           [entry.get("observed") for entry in full.actual
            if entry.get("check") == "trigger.is_triggered"
            and entry.get("target") == "SwitchB"] == [False]
           and [entry.get("observed") for entry in full.actual
                if entry.get("check") == "door.is_open"] == [False],
           json.dumps([entry.get("observed") for entry in full.actual]))
        ok("case3: no output transition was invented",
           [entry.get("observed") for entry in full.actual
            if entry.get("check") == "signal"] == [0],
           json.dumps([entry.get("observed") for entry in full.actual]))
        ok("case3: the partial case is unaffected by the unreachable source",
           reports["partial_conditions_block_output"].status == behavior.STATUS_PASS,
           json.dumps(reports["partial_conditions_block_output"].to_dict())[:300])
        write_text(fixture, fixture_original.decode("utf-8"))
        ok("case3: the unreachable-source fixture is restored byte-for-byte",
           sha256(fixture) == baseline["fixture"])

        # ---------------- Case 4: 观测不可用 ----------------
        print("=== Case 4: unavailable observations stay INSUFFICIENT ===")
        missing_target = probe([overlap("SwitchA"), advance(6)],
                               [{"check": "trigger.is_triggered", "target": "Absent",
                                 "equals": True}],
                               behavior_id="missing_target", tag="missing_target",
                               project=workspace.project)
        ok("case4: an unresolvable observation target -> INSUFFICIENT / check_unavailable",
           missing_target.get("status") == "INSUFFICIENT"
           and missing_target.get("reason") == "check_unavailable",
           json.dumps(missing_target)[:300])

        patch(fixture, '[node name="SwitchA" parent="." instance=ExtResource("2_switch")]',
              '[node name="SwitchA_moved" parent="." instance=ExtResource("2_switch")]')
        reports = verify_in_workspace()
        partial = reports["partial_conditions_block_output"]
        ok("case4: a missing precondition source -> INSUFFICIENT / precondition_unmet",
           partial.status == behavior.STATUS_INSUFFICIENT
           and partial.reason == "precondition_unmet",
           json.dumps(partial.to_dict())[:300])
        ok("case4: the unavailable precondition is reported as UNAVAILABLE",
           any(entry.get("status") == "UNAVAILABLE"
               for entry in partial.preconditions),
           json.dumps(partial.preconditions)[:300])
        ok("case4: every behavior that observes the renamed node is INSUFFICIENT, none PASS",
           all(report.status == behavior.STATUS_INSUFFICIENT
               for report in reports.values())
           and not any(report.status == behavior.STATUS_PASS
                       for report in reports.values()),
           json.dumps({name: report.status for name, report in reports.items()}))
        write_text(fixture, fixture_original.decode("utf-8"))
        ok("case4: the renamed-target fixture is restored byte-for-byte",
           sha256(fixture) == baseline["fixture"])
    finally:
        workspace.close()

    # ---------------- Case 5: 契约边界 ----------------
    print("=== Case 5: behavior scenes stay inside the Feature directory ===")
    for name, value, needle in (
        ("gate_scene_parent", "../chase_movement/ChaseTargetFixture.tscn",
         "relative path inside"),
        ("gate_scene_absolute", "F:/tmp/escape.tscn", "relative path inside"),
        ("gate_scene_res", FIXTURE_SCENE, "relative path inside"),
        ("gate_scene_missing", "Missing.tscn", "scene not found"),
        ("gate_scene_extension", "fixture.txt", ".tscn"),
    ):
        contracts, reports = build_feature(name, [{
            "id": "x",
            "scene": value,
            "actions": [overlap("SwitchA")],
            "expected": [{"check": "node.exists", "target": ".", "equals": True}],
        }])
        detail = reports[0].detail if reports else "contract accepted"
        ok("case5: scene %r rejected" % value,
           not contracts and bool(reports)
           and reports[0].status == behavior.STATUS_INVALID and needle in detail, detail)

    illegal_action, illegal_reports = build_feature("gate_illegal_action", [{
        "id": "x",
        "scene": "Probe.tscn",
        "actions": [{"type": "condition_gate.set_condition",
                     "target": ".", "params": {"value": True, "id": "a"}}],
        "expected": [{"check": "node.exists", "target": ".", "equals": True}],
    }], files={"Probe.tscn": "[gd_scene format=3]\n"})
    ok("case5: an undeclared action is rejected instead of executed",
       not illegal_action and bool(illegal_reports)
       and illegal_reports[0].status == behavior.STATUS_INVALID,
       illegal_reports[0].detail if illegal_reports else "accepted")

    # ---------------- Case 6: CLI 与恢复 ----------------
    print("=== Case 6: the CLI reports the repository Feature and a real defect ===")
    clean = subprocess.run([sys.executable, CLI, "--feature", FEATURE],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=300, stdin=subprocess.DEVNULL,
                           cwd=PROJECT_ROOT)
    clean_lines = [line.strip().split() for line in (clean.stdout or "").splitlines()
                   if line.strip().startswith(FEATURE)]
    ok("case6: the CLI reports three PASS behaviors for the repository Feature",
       clean.returncode == 0 and len(clean_lines) == 3
       and all(row[2] == "PASS" for row in clean_lines)
       and [row[1] for row in clean_lines] == list(BEHAVIORS),
       "exit=%s out=%s" % (clean.returncode, (clean.stdout or "")[-400:]))

    copy_root = os.path.join(_tempdir, "cli", "Features")
    shutil.copytree(FEATURES, copy_root)
    cli_script = os.path.join(copy_root, FEATURE, "condition_gate.gd")
    cli_original = read_bytes(cli_script)
    write_text(cli_script, cli_original.decode("utf-8").replace(
        "\t\tif condition_count > _states.size():\n\t\t\tmet = false\n", ""))
    proc = subprocess.run([sys.executable, CLI, "--feature", FEATURE,
                           "--features-dir", copy_root], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300,
                          stdin=subprocess.DEVNULL, cwd=PROJECT_ROOT)
    ok("case6: the CLI exits non-zero for a real gating defect",
       proc.returncode == 1 and "MISMATCH" in (proc.stdout or ""),
       "exit=%s out=%s" % (proc.returncode, (proc.stdout or "")[-300:]))
    with open(cli_script, "wb") as handle:
        handle.write(cli_original)
    ok("case6: the CLI defect copy is restored byte-for-byte",
       sha256(cli_script) == baseline["script"])

    ok("case6: repository Feature files are untouched",
       sha256(os.path.join(FEATURES, FEATURE, "condition_gate.gd")) == baseline["script"]
       and sha256(os.path.join(FEATURES, FEATURE, "ConditionGateFixture.tscn"))
       == baseline["fixture"]
       and sha256(os.path.join(FEATURES, FEATURE, "template.yaml")) == baseline["template"])

    protocol_after = behavior_protocol.load_protocol()
    # Phase 1.46 追加了 gate.is_fulfilled 观测与 gate.fulfilled 信号（组合场景链所需，
    # 供单个 Feature 契约与组合契约共用）；actions 能力表本阶段未增加。
    # Phase 1.49 追加了 stun.stunned 信号（眩晕证据需要观测跨越广播）；
    # Phase 1.50 追加了 health_bar.ratio 观测（血条只读显示状态）。
    # Phase 1.52 追加了 cooldown.start / screenshake.add_trauma 动作、cooldown.is_ready
    # 等观测与 6 个自释放组件终止信号（cooldown / i_frames / screen_shake / hit_flash /
    # projectile / patrol_movement）。
    # 协议可随其它 Feature 扩展；固定本 Feature 所依赖的动作、观测和信号，
    # 并由 manifest/运行时证据检查协议有效性，不锁共享协议总量。
    required = {
        "actions": {"simulation.advance_frames"},
        "observations": {"gate.is_fulfilled"},
        "signals": {"gate.fulfilled"},
    }
    ok("case6: condition-gate protocol dependencies remain registered",
       protocol_after.version == behavior_protocol.SUPPORTED_PROTOCOL_VERSION
       and all(required[k] <= set(getattr(protocol_after, k)) for k in required),
       "version=%s missing=%s" % (
           getattr(protocol_after, "version", "?"),
           {k: sorted(values - set(getattr(protocol_after, k)))
            for k, values in required.items()}))


if __name__ == "__main__":
    sys.exit(main())
