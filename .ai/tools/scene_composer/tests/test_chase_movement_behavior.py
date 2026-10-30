#!/usr/bin/env python3
"""追逐行为证据测试（Phase 1.43）

Phase 1.42 已有真实帧推进与时间点观测；本阶段证明这些能力可以直接复用到
`chase_movement`，不需要新增任何协议动作：

    Case 1  正向证据：approach_target / hold_without_target 均 PASS，2/2 重放一致
    Case 2  真实缺陷：冻结追击 / 无目标乱走 → MISMATCH（且互不影响）
    Case 3  目标不可达（改夹具场景）→ MISMATCH，而不是 PASS
    Case 4  观测不可用 → INSUFFICIENT；观测窗口不足 → MISMATCH
    Case 5  行为级证据场景（`behavior[].scene`）：合法夹具被接受，
            绝对路径 / res:// / .. / 非 .tscn / 缺失文件 → INVALID
    Case 6  CLI 对真实缺陷返回非 0；所有注入副本按 SHA256 恢复

`chase_movement` 的入口场景本身不配置 target_path（组件只负责朝目标移动），
因此 approach_target 使用同目录的 `ChaseTargetFixture.tscn`：容器根 + Chaser +
静止 Target。`scene` 只选择证据场景，不增加动作、观测或写入能力。

用法:
    python .ai/tools/scene_composer/tests/test_chase_movement_behavior.py
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

FEATURE = "chase_movement"
FIXTURE_SCENE = "res://Features/chase_movement/ChaseTargetFixture.tscn"
ENTRY_SCENE = "res://Features/chase_movement/ChaseMovement.tscn"


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


def probe(actions, expected, scene=FIXTURE_SCENE, window_frames=1,
          preconditions=None, behavior_id="case", tag="", project=""):
    contract = {"feature": FEATURE, "behavior": behavior_id,
                "run_id": "chase-%s-%s" % (behavior_id, tag or behavior_id),
                "replay_index": 1, "window_frames": window_frames, "scene": scene,
                "actions": actions, "preconditions": preconditions or [],
                "expected": expected}
    observation = behavior.run_probe(contract, project or PROJECT_ROOT, _godot,
                                     timeout_s=60)
    return observation.get("result") or {}


def advance(frames):
    return {"type": "simulation.advance_frames", "params": {"frames": frames}}


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


def rejected_scene(name: str, scene_value, needle: str) -> None:
    contracts, reports = build_feature(name, [{
        "id": "x",
        "scene": scene_value,
        "actions": [advance(1)],
        "expected": [{"check": "node.exists", "target": ".", "equals": True}],
    }])
    detail = reports[0].detail if reports else "contract accepted"
    ok("case5: scene %r rejected" % scene_value,
       not contracts and bool(reports) and reports[0].status == behavior.STATUS_INVALID
       and needle in detail, detail)


def main() -> int:
    global _godot, _tempdir
    _godot = runtime_evidence.find_godot(PROJECT_ROOT)
    if not _godot:
        print("SKIP: godot executable not found; chase behavior cannot be verified")
        return 1
    os.makedirs(os.path.join(DOTAI, "tmp"), exist_ok=True)
    _tempdir = tempfile.mkdtemp(prefix="chase_behavior_", dir=os.path.join(DOTAI, "tmp"))
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
    print("PASS: all chase behavior checks passed")
    return 0


def run_cases() -> None:
    protocol = behavior_protocol.load_protocol()

    # ---------------- Case 1: 真实证据 + 重放 ----------------
    print("=== Case 1: chase_movement executes real physics-frame chasing ===")
    workspace = behavior.BehaviorWorkspace(FEATURES, _godot)
    try:
        reports = behavior.verify_feature(FEATURE, FEATURES, FEATURES, _godot,
                                          replay=2, workspace=workspace)
        by_id = {report.behavior: report for report in reports}
        ok("case1: both behaviors were checked", set(by_id) ==
           {"approach_target", "hold_without_target"}, str(sorted(by_id)))
        for name in ("approach_target", "hold_without_target"):
            report = by_id.get(name)
            ok("case1: %s PASS with two consistent replays" % name,
               report is not None and report.status == behavior.STATUS_PASS
               and report.replay_count == 2 and report.replay_consistent,
               json.dumps(report.to_dict())[:400] if report else "missing")
            ok("case1: %s executed the real frame action" % name,
               report is not None and report.action_executed
               and (report.runs[0].get("actions") or [{}])[0].get("executed") is True)
        approach = by_id.get("approach_target")
        if approach:
            values = {check.get("check"): check.get("observed")
                      for check in approach.actual}
            displacement = [check.get("observed") for check in approach.actual
                            if check.get("check") == "node2d.displacement"]
            ok("case1: the chaser really closed ~59 px in 60 physics frames",
               any(isinstance(value, (int, float)) and 57.5 <= float(value) <= 62.5
                   for value in displacement),
               str(values))
            ok("case1: the chaser did not drift on the other axis",
               any(value == 0.0 for value in displacement[1:]), str(displacement))
        hold = by_id.get("hold_without_target")
        if hold:
            ok("case1: without a target the chaser stays still",
               all(check.get("observed") == 0.0 for check in hold.actual),
               str([check.get("observed") for check in hold.actual]))
        contracts, _ = behavior.build_contracts(FEATURE, FEATURES)
        ok("case1: the fixture scene is used only by the declared behavior",
           [contract["scene"] for contract in contracts] == [FIXTURE_SCENE, ENTRY_SCENE],
           str([contract["scene"] for contract in contracts]))
        if contracts:
            ok("case1: the fixture contract stays inside the frame budget",
               protocol.frame_budget_errors(contracts[0]["actions"],
                                            contracts[0]["window_frames"]) == [])

        # ---------------- Case 2: 真实缺陷 ----------------
        print("=== Case 2: real defects produce MISMATCH, not PASS ===")
        baseline = {
            "script": sha256(os.path.join(FEATURES, FEATURE, "chase_movement.gd")),
            "fixture": sha256(os.path.join(FEATURES, FEATURE, "ChaseTargetFixture.tscn")),
            "template": sha256(os.path.join(FEATURES, FEATURE, "template.yaml")),
        }
        workspace_features = os.path.join(workspace.project, "Features")
        script = os.path.join(workspace_features, FEATURE, "chase_movement.gd")
        fixture = os.path.join(workspace_features, FEATURE, "ChaseTargetFixture.tscn")

        def verify_in_workspace():
            return {report.behavior: report
                    for report in behavior.verify_feature(
                        FEATURE, FEATURES, workspace.project, _godot,
                        replay=1, workspace=workspace)}

        def patch(path, old, new):
            with open(path, "rb") as handle:
                original = handle.read()
            text = original.decode("utf-8")
            if old not in text:
                raise AssertionError("patch anchor not found in %s" % path)
            write_text(path, text.replace(old, new, 1))
            return original

        def restore(path, original):
            with open(path, "wb") as handle:
                handle.write(original)

        frozen = patch(script,
                       "\tvelocity = (_target.global_position - global_position).normalized() * speed\n"
                       "\tmove_and_slide()",
                       "\tvelocity = Vector2.ZERO")
        reports = verify_in_workspace()
        ok("case2: a frozen chaser -> MISMATCH / state_mismatch",
           reports["approach_target"].status == behavior.STATUS_MISMATCH
           and reports["approach_target"].reason == "state_mismatch",
           json.dumps(reports["approach_target"].to_dict())[:300])
        ok("case2: the no-target control still passes while chasing is broken",
           reports["hold_without_target"].status == behavior.STATUS_PASS,
           json.dumps(reports["hold_without_target"].to_dict())[:300])
        restore(script, frozen)
        ok("case2: the frozen-chaser script is restored byte-for-byte",
           sha256(script) == baseline["script"])

        wandering = patch(script,
                          "\t\tif _target == null:\n\t\t\tvelocity = Vector2.ZERO\n\t\t\treturn",
                          "\t\tif _target == null:\n"
                          "\t\t\tvelocity = Vector2(speed, 0.0)\n"
                          "\t\t\tmove_and_slide()\n\n\t\t\treturn")
        reports = verify_in_workspace()
        ok("case2: a chaser that wanders without a target -> MISMATCH",
           reports["hold_without_target"].status == behavior.STATUS_MISMATCH,
           json.dumps(reports["hold_without_target"].to_dict())[:300])
        ok("case2: the approach control still passes while idling is broken",
           reports["approach_target"].status == behavior.STATUS_PASS,
           json.dumps(reports["approach_target"].to_dict())[:300])
        restore(script, wandering)
        ok("case2: the wandering script is restored byte-for-byte",
           sha256(script) == baseline["script"])

        # ---------------- Case 3: 目标不可达 ----------------
        print("=== Case 3: an unreachable target cannot PASS ===")
        broken_target = patch(fixture, 'target_path = NodePath("../Target")',
                              'target_path = NodePath("../Absent")')
        reports = verify_in_workspace()
        ok("case3: a misconfigured target -> MISMATCH, never PASS",
           reports["approach_target"].status == behavior.STATUS_MISMATCH,
           json.dumps(reports["approach_target"].to_dict())[:300])
        ok("case3: the no-target behavior is unaffected by the broken fixture",
           reports["hold_without_target"].status == behavior.STATUS_PASS,
           json.dumps(reports["hold_without_target"].to_dict())[:300])
        restore(fixture, broken_target)
        ok("case3: the fixture scene is restored byte-for-byte",
           sha256(fixture) == baseline["fixture"])
    finally:
        workspace.close()

    # ---------------- Case 4: 观测不足 ----------------
    print("=== Case 4: unavailable observations and short windows do not PASS ===")
    unavailable = probe([advance(1)],
                        [{"check": "node2d.displacement", "target": "Absent",
                          "axis": "x", "min": 0.0}],
                        behavior_id="unavailable", tag="unavailable")
    ok("case4: an unresolvable observation target -> INSUFFICIENT / check_unavailable",
       unavailable.get("status") == "INSUFFICIENT"
       and unavailable.get("reason") == "check_unavailable",
       json.dumps(unavailable)[:300])
    short = probe([advance(1)],
                  [{"check": "node2d.displacement", "target": "Chaser", "axis": "x",
                    "min": 57.5, "max": 62.5}],
                  behavior_id="short_window", tag="short_window")
    ok("case4: one frame is not enough evidence for a 60-frame expectation -> MISMATCH",
       short.get("status") == "MISMATCH"
       and (short.get("checks") or [{}])[0].get("observed", 0) < 57.5,
       json.dumps(short)[:300])

    # ---------------- Case 5: 行为级证据场景 ----------------
    print("=== Case 5: behavior scenes stay inside the Feature directory ===")
    for name, value, needle in (
        ("scene_parent", "../escape.tscn", "relative path inside"),
        ("scene_absolute", "/tmp/escape.tscn", "relative path inside"),
        ("scene_res", "res://Features/chase_movement/ChaseTargetFixture.tscn",
         "relative path inside"),
        ("scene_missing", "Missing.tscn", "scene not found"),
        ("scene_extension", "fixture.txt", ".tscn"),
    ):
        rejected_scene(name, value, needle)
    nested = build_feature("scene_nested", [{
        "id": "x", "scene": "fixtures/Nested.tscn", "actions": [advance(1)],
        "expected": [{"check": "node.exists", "target": ".", "equals": True}],
    }], files={"fixtures/Nested.tscn": "[gd_scene format=3]\n"})
    ok("case5: a nested relative fixture inside the Feature directory is accepted",
       len(nested[0]) == 1 and nested[0][0]["scene"]
       == "res://Features/scene_nested/fixtures/Nested.tscn"
       and nested[1] == [], str(nested[1][0].detail if nested[1] else nested[0]))

    # ---------------- Case 6: CLI 与恢复 ----------------
    print("=== Case 6: the CLI fails on a real defect and copies are restored ===")
    copy_root = os.path.join(_tempdir, "cli", "Features")
    shutil.copytree(FEATURES, copy_root)
    cli_script = os.path.join(copy_root, FEATURE, "chase_movement.gd")
    with open(cli_script, "rb") as handle:
        cli_original = handle.read()
    write_text(cli_script, cli_original.decode("utf-8").replace(
        "\tvelocity = (_target.global_position - global_position).normalized() * speed",
        "\tvelocity = Vector2.ZERO"))
    proc = subprocess.run([sys.executable, CLI, "--feature", FEATURE,
                           "--features-dir", copy_root], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300,
                          stdin=subprocess.DEVNULL, cwd=PROJECT_ROOT)
    ok("case6: the CLI exits non-zero for a real chase defect",
       proc.returncode == 1 and "MISMATCH" in (proc.stdout or ""),
       "exit=%s out=%s" % (proc.returncode, (proc.stdout or "")[-200:]))
    with open(cli_script, "wb") as handle:
        handle.write(cli_original)
    ok("case6: the CLI fixture is restored byte-for-byte",
       sha256(cli_script) == baseline["script"])

    ok("case6: repository Feature files are untouched",
       sha256(os.path.join(FEATURES, FEATURE, "chase_movement.gd")) == baseline["script"]
       and sha256(os.path.join(FEATURES, FEATURE, "ChaseTargetFixture.tscn"))
       == baseline["fixture"]
       and sha256(os.path.join(FEATURES, FEATURE, "template.yaml")) == baseline["template"])


if __name__ == "__main__":
    sys.exit(main())
