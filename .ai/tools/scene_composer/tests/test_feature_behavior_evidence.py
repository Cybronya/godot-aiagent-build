#!/usr/bin/env python3
"""Feature Behavior Evidence 测试（Phase 1.40）

真实 Godot 场景 + 受限注册动作 → 观测后置状态 → 重放一致性 / 负向对照。

    Case 1  仓库 4 个 Feature / 6 个 behavior → 真实动作后 PASS（含观测值）
    Case 2  动作入口不存在但状态凑巧符合 → INSUFFICIENT（绝不 PASS）
    Case 3  动作执行但状态不变（观察窗口耗尽）→ MISMATCH，wait 满窗口
    Case 4  动作执行但状态错误变化 → MISMATCH
    Case 5  前置条件不满足 → INSUFFICIENT / precondition_unmet，动作未执行
    Case 6  非法动作 / 参数 / 检查 / 目标 / 窗口 / 重复 id → INVALID，不启动 Godot
    Case 7  未声明 behavior → NOT_DECLARED，不启动 Godot
    Case 8  采集失败（无结果）→ INSUFFICIENT，绝不 PASS
    Case 9  重放结果不一致 → INSUFFICIENT / replay_inconsistent，绝不 PASS
    Case 10 CLI 退出码：PASS=0；MISMATCH=1；INSUFFICIENT 默认 0 / --require-behavior=1；INVALID=1
    Case 11 真实黄金 Feature 副本上的负向对照（哈希记录 + 逐字节恢复）
    Case 12 Phase 1.38 静态对账与 Phase 1.39 运行时实例证据继续 PASS
    Case 13 零帧推进 + 纯否定期望的契约 -> INVALID（误报修复回归，Phase 1.45）

所有夹具位于 `.ai/tmp/` 的临时目录（独立 Features 副本），不写仓库 Features；
测试结束删除临时目录。

用法:
    python .ai/tools/scene_composer/tests/test_feature_behavior_evidence.py
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
TOOL_DIR = os.path.dirname(_HERE)
TOOLS_DIR = os.path.dirname(TOOL_DIR)
DOTAI = os.path.dirname(TOOLS_DIR)
PROJECT_ROOT = os.path.dirname(DOTAI)
FEATURES = os.path.join(PROJECT_ROOT, "Features")

for path in (TOOL_DIR, TOOLS_DIR, _HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import feature_behavior_evidence as behavior                    # noqa: E402
import instance_evidence                                        # noqa: E402
import runtime_instance_evidence as runtime_evidence            # noqa: E402

_failures = []

SET_OPEN_BLOCK = ("func set_open(value: bool) -> void:\n"
                  "\tif _is_open == value:\n"
                  "\t\treturn\n"
                  "\t_apply(value)\n")

PASS_BEHAVIOR = """behavior:
  - id: open
    actions:
      - {type: door.set_open, target: ".", params: {value: true}}
    preconditions:
      - {check: door.is_open, target: ".", equals: false}
    expected:
      - {check: door.is_open, target: ".", equals: true}
      - {check: signal, entry: door.state_changed, target: ".", count: 1, last_args: [true]}
    window_frames: 5
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


def door_template(behavior_yaml: str, feature_id: str = "openable_door") -> str:
    return ("feature:\n  id: %s\nscene:\n  source: OpenableDoor.tscn\n"
            "validation:\n  required_nodes:\n    - OpenableDoor\n" % feature_id) + behavior_yaml


def make_features(root: str, name: str) -> str:
    path = os.path.join(root, name, "Features")
    os.makedirs(path, exist_ok=True)
    return path


def copy_door(features_dir: str, template: str = PASS_BEHAVIOR,
              start_open: bool = False) -> dict:
    """复制真实 openable_door Feature 到隔离 Features 目录。"""
    dest = os.path.join(features_dir, "openable_door")
    shutil.copytree(os.path.join(FEATURES, "openable_door"), dest)
    write_text(os.path.join(dest, "template.yaml"), door_template(template))
    if start_open:
        scene_path = os.path.join(dest, "OpenableDoor.tscn")
        text = read_text(scene_path)
        text = text.replace("script = ExtResource(\"1_door\")\n",
                            "script = ExtResource(\"1_door\")\nstart_open = true\n")
        write_text(scene_path, text)
    return {"features": features_dir, "dir": dest,
            "script": os.path.join(dest, "openable_door.gd"),
            "scene": os.path.join(dest, "OpenableDoor.tscn")}


def run_feature(feature: str, features_dir: str, godot: str, replay: int = 1):
    return behavior.verify_feature(feature, features_dir=features_dir, godot=godot,
                                   replay=replay)


def checks_of(report) -> dict:
    return {(check.get("check"), check.get("target")): check for check in report.actual}


def stub_observation(payload) -> dict:
    return {"result": payload, "stdout": "", "stderr": "", "exit_code": 0,
            "duration": 0.01, "timed_out": False, "artifacts": {}}


def pass_payload() -> dict:
    return {"status": "PASS", "reason": "ok", "detail": "", "action_executed": True,
            "actions": [{"type": "door.set_open", "executed": True}],
            "preconditions": [],
            "checks": [{"check": "door.is_open", "target": ".", "entry": "",
                        "expected": True, "observed": True, "status": "PASS",
                        "first_observed_frame": 0}],
            "window_frames": 5, "waited_frames": 0}


def main() -> int:
    godot = runtime_evidence.find_godot(PROJECT_ROOT)
    if not godot:
        print("SKIP: godot executable not found; behavior evidence cannot be verified")
        return 1

    temp = tempfile.mkdtemp(prefix="behavior_tests_", dir=os.path.join(DOTAI, "tmp"))
    try:
        # ---------------- Case 1: 仓库 Feature 的真实行为证据 ----------------
        print("=== Case 1: repository Features execute real actions ===")
        declared = behavior.declared_features()
        legacy_features = ["collect_pickup", "heal_pickup", "health", "openable_door"]
        ok("case1: the Phase 1.40 Features still declare behavior",
           [feature for feature in declared if feature in legacy_features] == legacy_features,
           str(declared))
        time_driven_features = ["moving_platform", "player_movement", "trigger_switch"]
        ok("case1: Phase 1.42 time-driven Features declare behavior",
           set(time_driven_features).issubset(declared), str(declared))
        ok("case1: Phase 1.43 chase_movement declares behavior",
           {"chase_movement"}.issubset(declared), str(declared))
        ok("case1: Phase 1.44 condition_gate declares behavior",
           {"condition_gate"}.issubset(declared), str(declared))
        ok("case1: Phase 1.47 contact_damage, Phase 1.49 stun and Phase 1.50 "
           "health_bar declare behavior",
           set(legacy_features + time_driven_features
               + ["chase_movement", "condition_gate", "contact_damage",
                  "stun", "health_bar"]).issubset(declared), str(declared))
        # Phase 1.52：code_library 批量资产（片段 → Feature 流水线产物）全部补齐行为契约。
        code_library_features = ["cooldown", "hit_flash", "i_frames", "patrol_movement",
                                 "projectile", "screen_shake"]
        ok("case1: Phase 1.52 code-library Features declare behavior",
           set(code_library_features).issubset(declared), str(declared))
        # Phase 1.50：最后一个没有行为契约的正式 Feature（health_bar）已补齐；
        # 枚举来源是目录本身（凡是带 template.yaml 的 Feature 目录），不是 declared 自己。
        templated = sorted(name for name in os.listdir(FEATURES)
                           if os.path.isfile(os.path.join(FEATURES, name, "template.yaml")))
        ok("case1: every Feature with a template now declares behavior",
           templated == declared and "health_bar" in declared,
           "declared=%s templated=%s" % (declared, templated))
        workspace = behavior.BehaviorWorkspace(FEATURES, godot)
        reports = []
        try:
            for feature in declared:
                reports.extend(behavior.verify_feature(
                    feature, FEATURES, FEATURES, godot, replay=2, workspace=workspace))
        finally:
            workspace.close()
        ok("case1: legacy + time-driven + Phase 1.43-1.50 + Phase 1.52 behaviors "
           "are checked (49 total)",
           len(reports) == 49, str(len(reports)))
        ok("case1: the five health_bar behaviors are checked",
           {(report.feature, report.behavior) for report in reports} >= {
               ("health_bar", "initial_health_bar_ratio"),
               ("health_bar", "damage_updates_health_bar"),
               ("health_bar", "healing_updates_health_bar"),
               ("health_bar", "death_empties_health_bar"),
               ("health_bar", "unbound_bar_reports_no_fill")},
           str(sorted((report.feature, report.behavior) for report in reports)))
        ok("case1: the five stun behaviors are checked",
           {(report.feature, report.behavior) for report in reports} >= {
               ("stun", "hit_stuns_and_freezes_host"),
               ("stun", "stun_expires_and_host_resumes"),
               ("stun", "heal_does_not_stun"),
               ("stun", "death_guard_rejects_stun"),
               ("stun", "reentry_extends_without_rebroadcast")},
           str(sorted((report.feature, report.behavior) for report in reports)))
        ok("case1: the three contact_damage behaviors are checked",
           {(report.feature, report.behavior) for report in reports} >= {
               ("contact_damage", "damage_on_contact"),
               ("contact_damage", "no_damage_without_contact"),
               ("contact_damage", "damage_amount_is_respected")},
           str(sorted((report.feature, report.behavior) for report in reports)))
        ok("case1: the three condition_gate behaviors are checked",
           {(report.feature, report.behavior) for report in reports} >= {
               ("condition_gate", "partial_conditions_block_output"),
               ("condition_gate", "all_conditions_fulfill"),
               ("condition_gate", "condition_fallback_withdraws_output")},
           str(sorted((report.feature, report.behavior) for report in reports)))
        ok("case1: the eight legacy behaviors are still checked (health gained the "
           "two Phase 1.51 ones)",
           {(report.feature, report.behavior) for report in reports} >= {
               ("openable_door", "open"), ("health", "damage"), ("health", "death"),
               ("health", "heal_clamped"), ("health", "overkill_clamps_at_zero"),
               ("health", "post_death_guard"),
               ("collect_pickup", "collect_on_contact"),
               ("heal_pickup", "heal_damaged_target")},
           str(sorted((report.feature, report.behavior) for report in reports)))
        for report in reports:
            ok("case1: %s/%s PASS" % (report.feature, report.behavior),
               report.status == behavior.STATUS_PASS,
               json.dumps(report.to_dict(), ensure_ascii=False)[:500])
            ok("case1: %s/%s executed the real action" % (report.feature, report.behavior),
               report.action_executed and (report.runs[0].get("actions") or [{}])[0]
               .get("executed") is True)
            ok("case1: %s/%s replayed twice consistently" % (report.feature, report.behavior),
               report.replay_count == 2 and report.replay_consistent,
               str([run.get("status") for run in report.runs]))
            ok("case1: %s/%s records first_observed_frame" % (report.feature, report.behavior),
               isinstance(report.first_observed_frame, int) and report.first_observed_frame >= 0,
               str(report.first_observed_frame))
            ok("case1: %s/%s keeps evidence paths" % (report.feature, report.behavior),
               all(run.get("artifacts", {}).get("contract") for run in report.runs))

        by_behavior = {(report.feature, report.behavior): report for report in reports}
        door_checks = checks_of(by_behavior[("openable_door", "open")])
        ok("case1: door observed is_open=true",
           door_checks[("door.is_open", ".")]["observed"] is True,
           str(door_checks.get(("door.is_open", "."))))
        damage_checks = checks_of(by_behavior[("health", "damage")])
        ok("case1: health damage observed 1 (5-4)",
           damage_checks[("health.current", ".")]["observed"] == 1,
           str(damage_checks.get(("health.current", "."))))
        ok("case1: health damage emitted health_changed (1, 4)",
           damage_checks[("signal", ".")]["observed"] == 1,
           str(damage_checks.get(("signal", "."))))
        heal_checks = checks_of(by_behavior[("heal_pickup", "heal_damaged_target")])
        ok("case1: heal pickup raised the damaged target to 4",
           heal_checks[("health.current", "@actor/Health")]["observed"] == 4,
           str(heal_checks.get(("health.current", "@actor/Health"))))
        ok("case1: heal pickup was consumed after the real overlap",
           heal_checks[("node.freed", ".")]["observed"] is True,
           str(heal_checks.get(("node.freed", "."))))
        death_checks = checks_of(by_behavior[("health", "death")])
        ok("case1: lethal damage observed death",
           death_checks[("health.is_dead", ".")]["observed"] is True
           and death_checks[("health.current", ".")]["observed"] == 0,
           str(death_checks))
        protocol = behavior.behavior_protocol.load_protocol()
        ok("case1: every declared action is a registered action type",
           all(action.get("type") in protocol.actions
               for report in reports for action in report.actions))

        # ---------------- Case 2: 动作没执行不得 PASS ----------------
        print("=== Case 2: a missing entry point can never PASS ===")
        features = make_features(temp, "action_missing")
        missing_template = ("behavior:\n  - id: open\n"
                            "    actions: [{type: door.set_open, target: \".\", "
                            "params: {value: true}}]\n"
                            "    preconditions: []\n"
                            "    expected: [{check: door.is_open, target: \".\", "
                            "equals: true}]\n"
                            "    window_frames: 5\n")
        fixture = copy_door(features, template=missing_template, start_open=True)
        script = read_text(fixture["script"]).replace("func set_open(",
                                                      "func renamed_set_open(")
        write_text(fixture["script"], script)
        reports = run_feature("openable_door", features, godot)
        ok("case2: status INSUFFICIENT / action_unavailable",
           reports[0].status == behavior.STATUS_INSUFFICIENT
           and reports[0].reason == "action_unavailable",
           json.dumps(reports[0].to_dict())[:400])
        ok("case2: action_executed is false", reports[0].action_executed is False)
        ok("case2: an already-true expected state did not become PASS",
           reports[0].status != behavior.STATUS_PASS)

        # ---------------- Case 3/4/11: 真实副本负向对照 ----------------
        print("=== Case 3/4/11: negative controls on a real Feature copy ===")
        features = make_features(temp, "controls")
        fixture = copy_door(features)
        repo_scene = os.path.join(FEATURES, "openable_door", "OpenableDoor.tscn")
        repo_script = os.path.join(FEATURES, "openable_door", "openable_door.gd")
        repo_hashes = {repo_scene: sha256(repo_scene), repo_script: sha256(repo_script)}
        scene_bytes = open(fixture["scene"], "rb").read()
        script_bytes = open(fixture["script"], "rb").read()

        baseline = run_feature("openable_door", features, godot)[0]
        ok("case11: the untouched copy PASSes before the controls",
           baseline.status == behavior.STATUS_PASS, baseline.detail)
        baseline_hashes = {fixture["scene"]: sha256(fixture["scene"]),
                           fixture["script"]: sha256(fixture["script"])}

        # 对照 1：动作执行但状态不变（set_open 变 no-op）。
        write_text(fixture["script"], script_bytes.decode().replace(
            SET_OPEN_BLOCK, "func set_open(value: bool) -> void:\n\tpass\n"))
        report = run_feature("openable_door", features, godot)[0]
        ok("case11-control1: no-op action -> MISMATCH / state_mismatch",
           report.status == behavior.STATUS_MISMATCH and report.reason == "state_mismatch",
           json.dumps(report.to_dict())[:400])
        ok("case3: the whole observation window was waited",
           report.status != behavior.STATUS_PASS
           and report.runs[0].get("waited_frames") == report.window_frames,
           str(report.runs[0].get("waited_frames")))
        ok("case3: action was executed but the post-condition failed",
           report.action_executed is True)
        write_text(fixture["script"], script_bytes.decode())
        ok("case11-control1: script restored byte-for-byte",
           sha256(fixture["script"]) == baseline_hashes[fixture["script"]])

        # 对照 2：动作执行但状态错误变化（永远关门）。
        write_text(fixture["script"], script_bytes.decode().replace(
            "\t_apply(value)\n", "\t_apply(false)\n"))
        report = run_feature("openable_door", features, godot)[0]
        ok("case11-control2: wrong state change -> MISMATCH",
           report.status == behavior.STATUS_MISMATCH, report.detail)
        ok("case4: observed state is reported as false",
           report.actual[0].get("observed") is False, str(report.actual[0]))
        write_text(fixture["script"], script_bytes.decode())
        ok("case11-control2: script restored byte-for-byte",
           sha256(fixture["script"]) == baseline_hashes[fixture["script"]])

        # 对照 3：动作入口被移除（行为路径被破坏）。
        write_text(fixture["script"], script_bytes.decode().replace(
            "func set_open(", "func removed_set_open("))
        report = run_feature("openable_door", features, godot)[0]
        ok("case11-control3: removed entry point -> INSUFFICIENT / action_unavailable",
           report.status == behavior.STATUS_INSUFFICIENT
           and report.reason == "action_unavailable", report.detail)
        write_text(fixture["script"], script_bytes.decode())
        ok("case11-control3: script restored byte-for-byte",
           sha256(fixture["script"]) == baseline_hashes[fixture["script"]])

        ok("case11: the copy is restored (scene + script)",
           {fixture["scene"]: sha256(fixture["scene"]),
            fixture["script"]: sha256(fixture["script"])} == baseline_hashes)
        ok("case11: repository golden Feature files are untouched",
           all(sha256(path) == digest for path, digest in repo_hashes.items()))
        ok("case11: scene file was never rewritten",
           sha256(fixture["scene"]) == hashlib.sha256(scene_bytes).hexdigest())

        # ---------------- Case 5: 前置条件不满足 ----------------
        print("=== Case 5: an unmet precondition stops before the action ===")
        features = make_features(temp, "precondition")
        unmet = PASS_BEHAVIOR.replace(
            "- {check: door.is_open, target: \".\", equals: false}",
            "- {check: door.is_open, target: \".\", equals: true}")
        copy_door(features, template=unmet)
        report = run_feature("openable_door", features, godot)[0]
        ok("case5: INSUFFICIENT / precondition_unmet",
           report.status == behavior.STATUS_INSUFFICIENT
           and report.reason == "precondition_unmet",
           json.dumps(report.to_dict())[:400])
        ok("case5: no action was executed", report.action_executed is False)
        ok("case5: the precondition observation is reported",
           report.preconditions and report.preconditions[0].get("status") == "STATE_MISMATCH",
           str(report.preconditions))

        # ---------------- Case 6: 非法契约（不启动 Godot） ----------------
        print("=== Case 6: invalid contracts are rejected without a Godot run ===")
        features = make_features(temp, "invalid")
        base = "feature:\n  id: %s\nscene:\n  source: X.tscn\nvalidation:\n  required_nodes:\n    - X\n"
        cases = {
            "bad_action": ("- id: a\n  actions: [{type: door.force_open}]\n"
                           "  expected: [{check: door.is_open, target: \".\", equals: true}]\n"),
            "bad_param": ("- id: a\n  actions: [{type: door.set_open, params: {value: 1}}]\n"
                          "  expected: [{check: door.is_open, target: \".\", equals: true}]\n"),
            "extra_param": ("- id: a\n  actions: [{type: door.set_open, "
                            "params: {value: true, forced: true}}]\n"
                            "  expected: [{check: door.is_open, target: \".\", equals: true}]\n"),
            "bad_check": ("- id: a\n  actions: [{type: door.set_open, params: {value: true}}]\n"
                          "  expected: [{check: door.is_shiny, target: \".\", equals: true}]\n"),
            "missing_equals": ("- id: a\n  actions: [{type: door.set_open, params: {value: true}}]\n"
                               "  expected: [{check: door.is_open, target: \".\"}]\n"),
            "bad_target": ("- id: a\n  actions: [{type: door.set_open, "
                           "params: {value: true}, target: \"../outside\"}]\n"
                           "  expected: [{check: door.is_open, target: \".\", equals: true}]\n"),
            "bad_window": ("- id: a\n  window_frames: 0\n"
                           "  actions: [{type: door.set_open, params: {value: true}}]\n"
                           "  expected: [{check: door.is_open, target: \".\", equals: true}]\n"),
            "no_group": ("- id: a\n  actions: [{type: physics.overlap, params: {}}]\n"
                         "  expected: [{check: node.freed, target: \".\", equals: true}]\n"),
            # 零帧推进 + 纯否定期望：首个观测点即满足，PASS 没有观测支撑（Phase 1.45）
            "no_evidence": ("- id: a\n"
                            "  actions: [{type: physics.overlap, params: {group: players}}]\n"
                            "  expected: [{check: trigger.is_triggered, target: \".\", "
                            "equals: false}]\n  window_frames: 30\n"),
        }
        for name, block in cases.items():
            directory = os.path.join(features, name)
            os.makedirs(directory, exist_ok=True)
            indented = "\n".join("  " + line for line in block.splitlines())
            write_text(os.path.join(directory, "template.yaml"),
                       (base % name) + "behavior:\n" + indented + "\n")
            reports = behavior.verify_feature(name, features_dir=features, godot="", replay=1)
            ok("case6: %s -> INVALID / contract_invalid" % name,
               reports[0].status == behavior.STATUS_INVALID
               and reports[0].reason == "contract_invalid",
               reports[0].detail)
            ok("case6: %s never launched Godot" % name,
               reports[0].run_id == "" or reports[0].replay_count == 0,
               str(reports[0].to_dict())[:200])
        reports = behavior.verify_feature("no_evidence", features_dir=features, godot="",
                                          replay=1)
        ok("case6: no_evidence names the missing observation window",
           reports[0].status == behavior.STATUS_INVALID
           and "observation window" in reports[0].detail, reports[0].detail)

        # 重复 id
        directory = os.path.join(features, "duplicate_id")
        os.makedirs(directory, exist_ok=True)
        write_text(os.path.join(directory, "template.yaml"),
                   (base % "duplicate_id") + "behavior:\n  " + PASS_BEHAVIOR.replace(
                       "behavior:\n  ", "") + "  " + PASS_BEHAVIOR.replace(
                       "behavior:\n  ", ""))
        reports = behavior.verify_feature("duplicate_id", features_dir=features, godot="",
                                          replay=1)
        ok("case6: duplicate behavior id -> INVALID",
           any(report.status == behavior.STATUS_INVALID
               and report.reason == "contract_invalid" for report in reports),
           str([report.detail for report in reports]))

        # ---------------- Case 7: 未声明 behavior ----------------
        print("=== Case 7: Features without behavior stay NOT_DECLARED ===")
        features = make_features(temp, "plain")
        directory = os.path.join(features, "plain_behavior")
        os.makedirs(directory, exist_ok=True)
        write_text(os.path.join(directory, "template.yaml"),
                   "feature:\n  id: plain_behavior\nscene:\n  source: Plain.tscn\n")
        report = behavior.verify_feature("plain_behavior", features_dir=features, godot="",
                                         replay=1)[0]
        ok("case7: NOT_DECLARED / behavior_not_declared",
           report.status == behavior.STATUS_NOT_DECLARED
           and report.reason == "behavior_not_declared", str(report.to_dict()))
        ok("case7: no Godot run for undeclared behavior", report.replay_count == 0)

        # ---------------- Case 8: 采集失败不得 PASS ----------------
        print("=== Case 8: collection failure is INSUFFICIENT, never PASS ===")
        def no_result(contract, project_root="", timeout_s=0, godot=""):
            return {"result": None, "stdout": "", "stderr": "", "exit_code": 0,
                    "duration": 0.01, "timed_out": False, "artifacts": {}}

        reports = behavior.verify_feature("openable_door", FEATURES, PROJECT_ROOT, "",
                                          replay=2, runner=no_result)
        ok("case8: INSUFFICIENT / evidence_unavailable",
           reports[0].status == behavior.STATUS_INSUFFICIENT
           and reports[0].reason == "evidence_unavailable", str(reports[0].to_dict()))
        original_find = behavior.runtime_evidence.find_godot
        behavior.runtime_evidence.find_godot = lambda root="": ""
        try:
            missing = behavior.verify_feature("openable_door", FEATURES, PROJECT_ROOT,
                                              "", replay=1)[0]
        finally:
            behavior.runtime_evidence.find_godot = original_find
        ok("case8: a missing Godot binary cannot become PASS",
           missing.status == behavior.STATUS_INSUFFICIENT, str(missing.to_dict())[:200])

        # ---------------- Case 9: 重放不一致不得 PASS ----------------
        print("=== Case 9: inconsistent replays never become PASS ===")
        calls = {"count": 0}

        def flaky(contract, project_root="", timeout_s=0, godot=""):
            calls["count"] += 1
            if calls["count"] % 2 == 1:
                return stub_observation(pass_payload())
            payload = pass_payload()
            payload["status"] = "MISMATCH"
            payload["reason"] = "state_mismatch"
            payload["checks"][0]["observed"] = False
            payload["checks"][0]["status"] = "STATE_MISMATCH"
            return stub_observation(payload)

        reports = behavior.verify_feature("openable_door", FEATURES, PROJECT_ROOT, "",
                                          replay=2, runner=flaky)
        ok("case9: INSUFFICIENT / replay_inconsistent",
           reports[0].status == behavior.STATUS_INSUFFICIENT
           and reports[0].reason == "replay_inconsistent", str(reports[0].to_dict())[:400])
        ok("case9: the two differing runs are preserved",
           [run.get("status") for run in reports[0].runs] == ["PASS", "MISMATCH"],
           str([run.get("status") for run in reports[0].runs]))

        # ---------------- Case 10: CLI 退出码 ----------------
        print("=== Case 10: CLI exit codes and machine-readable output ===")
        cli = [sys.executable, os.path.join(TOOL_DIR, "feature_behavior_evidence.py"),
               "--project-root", PROJECT_ROOT, "--godot", godot, "--replay", "1", "--json"]

        def cli_run(features_dir, feature="openable_door", extra=()):
            proc = subprocess.run(cli + ["--features-dir", features_dir,
                                         "--feature", feature] + list(extra),
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=180, stdin=subprocess.DEVNULL)
            return proc, json.loads(proc.stdout or "{}")

        features = make_features(temp, "cli_pass")
        copy_door(features)
        proc, payload = cli_run(features)
        ok("case10: PASS exits 0", proc.returncode == 0, proc.stdout[-300:])
        ok("case10: JSON exposes status/reason/action_executed/replay_consistent",
           payload.get("reports") and payload["reports"][0]["status"] == "PASS"
           and payload["reports"][0]["action_executed"] is True
           and payload["reports"][0]["replay_consistent"] is True
           and payload["reports"][0]["run_id"], str(payload)[:400])

        features = make_features(temp, "cli_noop")
        fixture = copy_door(features)
        write_text(fixture["script"], read_text(fixture["script"]).replace(
            SET_OPEN_BLOCK, "func set_open(value: bool) -> void:\n\tpass\n"))
        proc, payload = cli_run(features)
        ok("case10: MISMATCH exits 1", proc.returncode == 1, proc.stdout[-300:])
        ok("case10: MISMATCH JSON reports state_mismatch",
           payload["reports"][0]["status"] == "MISMATCH"
           and payload["reports"][0]["reason"] == "state_mismatch")

        features = make_features(temp, "cli_missing")
        fixture = copy_door(features, start_open=True)
        write_text(fixture["script"], read_text(fixture["script"]).replace(
            "func set_open(", "func renamed_set_open("))
        proc, _ = cli_run(features)
        ok("case10: INSUFFICIENT exits 0 without --require-behavior",
           proc.returncode == 0, proc.stdout[-300:])
        proc, _ = cli_run(features, extra=("--require-behavior",))
        ok("case10: INSUFFICIENT exits 1 under --require-behavior",
           proc.returncode == 1, proc.stdout[-300:])

        features = make_features(temp, "cli_invalid")
        directory = os.path.join(features, "bad_action")
        os.makedirs(directory, exist_ok=True)
        write_text(os.path.join(directory, "template.yaml"),
                   (base % "bad_action") + "behavior:\n"
                   "  - id: a\n    actions: [{type: door.force_open}]\n"
                   "    expected: [{check: door.is_open, target: \".\", equals: true}]\n")
        proc, payload = cli_run(features, feature="bad_action")
        ok("case10: INVALID exits 1", proc.returncode == 1, proc.stdout[-300:])
        ok("case10: invalid contract JSON reports contract_invalid",
           payload["reports"][0]["status"] == "INVALID"
           and payload["reports"][0]["reason"] == "contract_invalid")

        # ---------------- Case 12: 1.38 / 1.39 回归 ----------------
        print("=== Case 12: Phase 1.38 static and 1.39 runtime evidence still pass ===")
        for feature in instance_evidence.declared_features():
            ok("case12: %s static reconciliation PASS" % feature,
               instance_evidence.reconcile_feature(feature).status
               == instance_evidence.STATUS_PASS)
        for feature in runtime_evidence.declared_features():
            report = runtime_evidence.verify_feature(feature, godot=godot)
            ok("case12: %s runtime instance PASS" % feature,
               report.status == runtime_evidence.STATUS_PASS, report.detail)

        # ---------------- Case 13: 零帧 + 纯否定期望不得 PASS ----------------
        # Phase 1.45 误报复现与修复：接错后 1 帧内开关尚未触发，若契约只断言
        # 「未触发」且不推进任何帧，首个观测点就满足 → 修复前 PASS（waited 0），
        # 修复后 INVALID；补上真实帧推进后，同样的断言才真正看到矛盾 → MISMATCH。
        print("=== Case 13: a contract without an observation window cannot PASS ===")
        contract = {
            "feature": "trigger_switch", "behavior": "audit_no_evidence",
            "run_id": "no-evidence-1", "replay_index": 1, "window_frames": 30,
            "scene": "res://Features/trigger_switch/trigger_switch.tscn",
            "actions": [{"type": "physics.overlap", "target": ".",
                         "params": {"group": "players"}}],
            "preconditions": [{"check": "trigger.is_triggered", "target": ".",
                               "equals": False}],
            "expected": [{"check": "trigger.is_triggered", "target": ".",
                          "equals": False}],
        }
        payload = behavior.run_probe(contract, PROJECT_ROOT, godot, timeout_s=60) \
            .get("result") or {}
        ok("case13: zero-frame negative-only contract -> INVALID / contract_invalid",
           payload.get("status") == "INVALID"
           and payload.get("reason") == "contract_invalid"
           and "observation window" in str(payload.get("detail", "")),
           json.dumps(payload)[:400])
        ok("case13: the pre-fix PASS path is closed",
           payload.get("status") != "PASS", json.dumps(payload)[:300])

        with_frames = dict(contract)
        with_frames["behavior"] = "audit_with_frames"
        with_frames["run_id"] = "with-frames-1"
        with_frames["actions"] = list(contract["actions"]) + [
            {"type": "simulation.advance_frames", "params": {"frames": 6}}]
        payload2 = behavior.run_probe(with_frames, PROJECT_ROOT, godot, timeout_s=60) \
            .get("result") or {}
        ok("case13: with real frames the same expectation reports MISMATCH",
           payload2.get("status") == "MISMATCH"
           and payload2.get("reason") == "state_mismatch",
           json.dumps(payload2)[:400])
        ok("case13: the contradiction is the switch actually triggering",
           (payload2.get("checks") or [{}])[0].get("observed") is True,
           json.dumps(payload2.get("checks"))[:300])
    finally:
        shutil.rmtree(temp, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all behavior evidence checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
