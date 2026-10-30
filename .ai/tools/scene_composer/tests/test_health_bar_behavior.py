#!/usr/bin/env python3
"""血条行为证据测试（Phase 1.50）

`health_bar` 在 Phase 1.50 前只有 `Features/health_bar/test_health_bar.gd` 这一份**直接调用
`get_ratio()`** 的 Godot 单元测试：它能证明方法返回什么，但不能说明「真实受伤/治疗之后，
血条组件自己的显示状态确实跟着变了」，也没有负向对照与重放一致性。

本测试证明协议足以表达并判别这条显示链：

    Case 1  正向证据：5 条行为 PASS、2/2 重放一致、观测值可追溯、没有靠窗口等待
    Case 2  真实缺陷（隔离副本）：比例公式错误 / 比例不跟随 Health / 绑定失效 ——
            各自只打穿对应契约，相邻契约仍通过
    Case 3  证据不足：目标缺失 / 目标类型错误（没有 get_ratio）/ 前置条件不满足 → INSUFFICIENT
    Case 4  重放不一致 → INSUFFICIENT / replay_inconsistent
    Case 5  契约无效（窗口 0 / tolerance 无 equals / min > max / 参数名错误 / 类型错误）→ INVALID
    Case 6  CLI 对真实缺陷返回 1；隔离副本逐字节恢复；仓库文件哈希不变；manifest 未漂移

观测面：`health_bar.ratio` = `HealthBar.get_ratio()`，即 `_draw()` 用来算填充宽度
（`bar_size.x * ratio`）的那个值。它是**只读**的：本测试用「读三次比例不会让
`health_changed` 计数变化、也不会改变比例」来固定这一点。

用法:
    python .ai/tools/scene_composer/tests/test_health_bar_behavior.py
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

FEATURE = "health_bar"
FIXTURE_SCENE = "res://Features/health_bar/HealthBarFixture.tscn"
ENTRY_SCENE = "res://Features/health_bar/HealthBar.tscn"
SCRIPT = os.path.join("Features", FEATURE, "health_bar.gd")
FIXTURE = os.path.join("Features", FEATURE, "HealthBarFixture.tscn")
TEMPLATE = os.path.join("Features", FEATURE, "template.yaml")

INITIAL = "initial_health_bar_ratio"
DAMAGE = "damage_updates_health_bar"
HEALING = "healing_updates_health_bar"
DEATH = "death_empties_health_bar"
UNBOUND = "unbound_bar_reports_no_fill"
BEHAVIORS = (INITIAL, DAMAGE, HEALING, DEATH, UNBOUND)

BAR = "Host/Bar"
ORPHAN = "Orphan"
HEALTH = "Host/Health"


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def observed(report, check_name: str, target: str = ""):
    for check in report.actual if report else []:
        if check.get("check") == check_name and (not target
                                                 or check.get("target") == target):
            return check.get("observed")
    return None


def by_behavior(reports) -> dict:
    return {report.behavior: report for report in reports}


def probe(actions, expected, window_frames=5, preconditions=None,
          behavior_id="case", tag="", project="", scene=FIXTURE_SCENE,
          target_feature=FEATURE):
    contract = {"feature": target_feature, "behavior": behavior_id,
                "run_id": "health_bar-%s-%s" % (behavior_id, tag or behavior_id),
                "replay_index": 1, "window_frames": window_frames, "scene": scene,
                "actions": actions, "preconditions": preconditions or [],
                "expected": expected}
    observation = behavior.run_probe(contract, project or PROJECT_ROOT, _godot,
                                     timeout_s=60)
    return observation.get("result") or {}


def build_feature(name: str, behavior_block, files=None):
    features = os.path.join(_tempdir, "contracts")
    directory = os.path.join(features, name)
    body = yaml.safe_dump(behavior_block, allow_unicode=True, sort_keys=False)
    write_text(os.path.join(directory, "template.yaml"),
               "feature:\n  id: %s\nscene:\n  source: Probe.tscn\nbehavior:\n%s"
               % (name, textwrap.indent(body, "  ")))
    for relative, text in (files or {}).items():
        write_text(os.path.join(directory, relative), text)
    return behavior.build_contracts(name, features)


def invalid_case(label: str, behavior_block, needle: str) -> None:
    contracts, reports = build_feature(label, [behavior_block])
    detail = reports[0].detail if reports else "contract accepted"
    ok("case5: %s -> INVALID" % label,
       not contracts and bool(reports) and reports[0].status == behavior.STATUS_INVALID
       and needle in detail, detail)


def main() -> int:
    global _godot, _tempdir
    _godot = runtime_evidence.find_godot(PROJECT_ROOT)
    if not _godot:
        print("SKIP: godot executable not found; health_bar behaviour cannot be verified")
        return 1
    os.makedirs(os.path.join(DOTAI, "tmp"), exist_ok=True)
    _tempdir = tempfile.mkdtemp(prefix="health_bar_behavior_", dir=os.path.join(DOTAI, "tmp"))
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
    print("PASS: all health_bar behaviour checks passed")
    return 0


def run_cases() -> None:
    protocol = behavior_protocol.load_protocol()

    # ---------------- Case 1: 正向证据 ----------------
    print("=== Case 1: the bar is proven by real Health changes and real display state ===")
    contracts, _ = behavior.build_contracts(FEATURE, FEATURES)
    ok("case1: five behaviors are declared with the dedicated fixture",
       [contract["behavior"] for contract in contracts] == list(BEHAVIORS)
       and all(contract["scene"] == FIXTURE_SCENE for contract in contracts),
       str([(contract["behavior"], contract["scene"]) for contract in contracts]))
    ok("case1: the entry scene stays untouched by behaviour evidence",
       all(contract["scene"] != ENTRY_SCENE for contract in contracts)
       and os.path.isfile(os.path.join(FEATURES, FEATURE, "HealthBar.tscn")))
    ok("case1: the ratio observation is registered as a float observation",
       protocol.observation("health_bar.ratio").get("result", {}).get("type") == "float"
       and protocol.observation("health_bar.ratio").get("implemented") is True,
       str(protocol.observation("health_bar.ratio")))
    # 血条显示只依赖 Health 的真实动作，以及 health_bar.ratio 只读观测；
    # 不要求共享协议总量固定，也不允许为 UI 观测增添专用写入动作。
    ok("case1: bar evidence uses Health actions and no bar-specific write action",
       {"health.take_damage", "health.heal"} <= set(protocol.actions)
       and "health_bar.set_ratio" not in protocol.actions,
       str(sorted(protocol.actions)))

    workspace = behavior.BehaviorWorkspace(FEATURES, _godot)
    try:
        reports = behavior.verify_feature(FEATURE, FEATURES, FEATURES, _godot,
                                          replay=2, workspace=workspace)
        found = by_behavior(reports)
        ok("case1: every declared behavior was checked",
           set(found) == set(BEHAVIORS), str(sorted(found)))
        for name in BEHAVIORS:
            report = found.get(name)
            ok("case1: %s PASS with two consistent replays" % name,
               report is not None and report.status == behavior.STATUS_PASS
               and report.replay_count == 2 and report.replay_consistent,
               json.dumps(report.to_dict())[:400] if report else "missing")
            ok("case1: %s executed the real action" % name,
               report is not None and report.action_executed
               and all(record.get("executed") is True
                       for record in (report.runs[0].get("actions") or [])),
               json.dumps(report.runs[0].get("actions") if report else None)[:300])
            ok("case1: %s used no fixture action" % name,
               report is not None
               and not any(record.get("fixture") for record
                           in (report.runs[0].get("actions") or [])),
               json.dumps(report.runs[0].get("actions") if report else None)[:300])
            ok("case1: %s never needed the window to expire" % name,
               report is not None and int(report.runs[0].get("waited_frames") or 0) == 0,
               str(report.runs[0].get("waited_frames") if report else None))

        ok("case1: full health shows a full bar (1.0)",
           observed(found.get(INITIAL), "health_bar.ratio", BAR) == 1.0,
           str(observed(found.get(INITIAL), "health_bar.ratio", BAR)))
        ok("case1: 4 damage -> 6/10 = 0.6, with the real damage event",
           observed(found.get(DAMAGE), "health_bar.ratio", BAR) == 0.6
           and observed(found.get(DAMAGE), "health.current", HEALTH) == 6
           and observed(found.get(DAMAGE), "signal", HEALTH) == 1,
           json.dumps([{key: check.get(key) for key in ("check", "observed")}
                       for check in (found.get(DAMAGE).actual
                                     if found.get(DAMAGE) else [])]))
        ok("case1: damage 4 then heal 2 -> 8/10 = 0.8",
           observed(found.get(HEALING), "health_bar.ratio", BAR) == 0.8
           and observed(found.get(HEALING), "health.current", HEALTH) == 8
           and observed(found.get(HEALING), "signal", HEALTH) == 2,
           json.dumps([{key: check.get(key) for key in ("check", "observed")}
                       for check in (found.get(HEALING).actual
                                     if found.get(HEALING) else [])]))
        ok("case1: death empties the bar (0.0) and the host is dead",
           observed(found.get(DEATH), "health_bar.ratio", BAR) == 0.0
           and observed(found.get(DEATH), "health.is_dead", HEALTH) is True,
           json.dumps([{key: check.get(key) for key in ("check", "observed")}
                       for check in (found.get(DEATH).actual
                                     if found.get(DEATH) else [])]))
        ok("case1: the unbound bar reads 0.0 while Health is full (the observation "
           "reads the bar, not Health)",
           observed(found.get(UNBOUND), "health_bar.ratio", ORPHAN) == 0.0
           and observed(found.get(UNBOUND), "health_bar.ratio", BAR) == 1.0
           and observed(found.get(UNBOUND), "health.current", HEALTH) == 10,
           json.dumps([{key: check.get(key) for key in ("check", "target", "observed")}
                       for check in (found.get(UNBOUND).actual
                                     if found.get(UNBOUND) else [])]))

        # 只读性：同一条契约里读三次比例，值不变且不产生任何 health_changed。
        reads = probe([{"type": "health.take_damage", "target": HEALTH,
                        "params": {"amount": 4}},
                       {"type": "simulation.advance_frames", "params": {"frames": 1}}],
                      [{"check": "health_bar.ratio", "target": BAR, "equals": 0.6,
                        "tolerance": 0.0005},
                       {"check": "health_bar.ratio", "target": BAR, "equals": 0.6,
                        "tolerance": 0.0005},
                       {"check": "health_bar.ratio", "target": BAR, "equals": 0.6,
                        "tolerance": 0.0005},
                       {"check": "signal", "target": HEALTH,
                        "entry": "health.health_changed", "count": 1}],
                      behavior_id="read_only", tag="read_only")
        ok("case1: reading the ratio three times is side-effect free",
           reads.get("status") == "PASS"
           and [check.get("observed") for check in reads.get("checks", [])] == [0.6, 0.6, 0.6, 1],
           json.dumps({key: reads.get(key) for key in ("status", "checks")})[:400])

        # 同步语义：显示没有动画/延迟，1 帧窗口就足够（不靠长时间等待“等到对为止”）。
        minimal = probe([{"type": "health.take_damage", "target": HEALTH,
                         "params": {"amount": 4}},
                        {"type": "simulation.advance_frames", "params": {"frames": 1}}],
                       [{"check": "health_bar.ratio", "target": BAR, "equals": 0.6,
                         "tolerance": 0.0005}],
                       window_frames=1, behavior_id="minimal_window", tag="minimal")
        ok("case1: a one-frame window is already enough (no asynchronous display)",
           minimal.get("status") == "PASS" and minimal.get("waited_frames") == 0,
           json.dumps({key: minimal.get(key)
                       for key in ("status", "waited_frames", "checks")})[:400])

        # ---------------- Case 2: 真实缺陷 ----------------
        print("=== Case 2: each defect breaks exactly its own contract ===")
        baseline = {path: sha256(os.path.join(PROJECT_ROOT, path))
                    for path in (SCRIPT, FIXTURE, TEMPLATE)}
        script = os.path.join(workspace.project, SCRIPT)
        fixture = os.path.join(workspace.project, FIXTURE)

        def verify() -> dict:
            return by_behavior(behavior.verify_feature(
                FEATURE, FEATURES, workspace.project, _godot, replay=1,
                workspace=workspace))

        def patch(path: str, old: str, new: str) -> bytes:
            with open(path, "rb") as handle:
                original = handle.read()
            text = original.decode("utf-8")
            if text.count(old) != 1:
                raise AssertionError("patch anchor not unique/missing in %s: %r"
                                     % (os.path.basename(path), old))
            write_text(path, text.replace(old, new, 1))
            return original

        def restore(path: str, original: bytes) -> None:
            with open(path, "wb") as handle:
                handle.write(original)

        ratio_call = "\treturn float(_health.get_current_health()) / float(_health.max_health)\n"

        # 2a 比例公式错误：不再除以 max_health（0~1 → 0~max）。
        original = patch(script, ratio_call, "\treturn float(_health.get_current_health())\n")
        reports = verify()
        restore(script, original)
        broken = reports.get(INITIAL)
        ok("case2: a ratio that forgets max_health -> MISMATCH / state_mismatch",
           broken is not None and broken.status == behavior.STATUS_MISMATCH
           and broken.reason == "state_mismatch",
           json.dumps(broken.to_dict())[:300] if broken else "missing")
        ok("case2: the bar reports 10.0 instead of 1.0",
           observed(broken, "health_bar.ratio", BAR) == 10.0,
           str(observed(broken, "health_bar.ratio", BAR)))
        ok("case2: the damage contract is broken by the same formula (6.0 vs 0.6)",
           reports.get(DAMAGE).status == behavior.STATUS_MISMATCH
           and observed(reports.get(DAMAGE), "health_bar.ratio", BAR) == 6.0,
           json.dumps(reports.get(DAMAGE).to_dict())[:300])
        # 0/10 = 0.0 与 0/1 = 0.0 相同：死亡契约是 absence 型，看不到这个缺陷。
        ok("case2: the death contract cannot see it (0.0 either way)",
           reports.get(DEATH).status == behavior.STATUS_PASS,
           json.dumps(reports.get(DEATH).to_dict())[:300])
        # 未绑定血条仍读 0.0（它走的是 _health == null 的 guard），但 UNBOUND 契约整体失败，
        # 因为它同时断言了绑定血条的 1.0——这正好证明“观测确实读到了各自的节点”。
        ok("case2: the unbound bar still reads 0.0 while the bound one reports 10.0",
           observed(reports.get(UNBOUND), "health_bar.ratio", ORPHAN) == 0.0
           and observed(reports.get(UNBOUND), "health_bar.ratio", BAR) == 10.0,
           json.dumps({key: observed(reports.get(UNBOUND), "health_bar.ratio", key)
                       for key in (ORPHAN, BAR)}))
        ok("case2: the formula-patched script is restored byte-for-byte",
           sha256(script) == baseline[SCRIPT])

        # 2b 比例不跟随 Health：恒返回 1.0（“血条永远是满的”）。
        original = patch(script, ratio_call, "\treturn 1.0\n")
        reports = verify()
        restore(script, original)
        frozen = reports.get(DAMAGE)
        ok("case2: a bar stuck at full -> damage contract MISMATCH",
           frozen is not None and frozen.status == behavior.STATUS_MISMATCH
           and observed(frozen, "health_bar.ratio", BAR) == 1.0,
           json.dumps(frozen.to_dict())[:300] if frozen else "missing")
        ok("case2: healing and death are broken by the same stub",
           reports.get(HEALING).status == behavior.STATUS_MISMATCH
           and reports.get(DEATH).status == behavior.STATUS_MISMATCH,
           str({name: reports.get(name).status
                for name in (HEALING, DEATH)}))
        ok("case2: the initial contract still passes (full health is the stub value)",
           reports.get(INITIAL).status == behavior.STATUS_PASS,
           json.dumps(reports.get(INITIAL).to_dict())[:300])
        ok("case2: the stub-patched script is restored byte-for-byte",
           sha256(script) == baseline[SCRIPT])

        # 2c 显示绑定失效（等价于更新连接断开）：血条不再指向 Health。
        original = patch(fixture, 'health_path = NodePath("../Health")\n', "")
        reports = verify()
        restore(fixture, original)
        unbound = reports.get(DAMAGE)
        ok("case2: a torn-down binding -> damage contract MISMATCH",
           unbound is not None and unbound.status == behavior.STATUS_MISMATCH
           and observed(unbound, "health_bar.ratio", BAR) == 0.0,
           json.dumps(unbound.to_dict())[:300] if unbound else "missing")
        ok("case2: the bar reports 0.0 although Health dropped to 6",
           observed(unbound, "health.current", HEALTH) == 6,
           str(observed(unbound, "health.current", HEALTH)))
        ok("case2: initial and healing are broken by the same torn binding",
           reports.get(INITIAL).status == behavior.STATUS_MISMATCH
           and reports.get(HEALING).status == behavior.STATUS_MISMATCH,
           str({name: reports.get(name).status
                for name in (INITIAL, HEALING)}))
        # 绑定被拆后，未绑定血条的读数仍为 0.0（其 guard 未受影响），而死亡契约照旧成立。
        ok("case2: the unbound bar still reads 0.0 and death still passes",
           observed(reports.get(UNBOUND), "health_bar.ratio", ORPHAN) == 0.0
           and reports.get(DEATH).status == behavior.STATUS_PASS,
           json.dumps({name: reports.get(name).status
                       for name in (UNBOUND, DEATH)}))
        ok("case2: the binding-patched fixture is restored byte-for-byte",
           sha256(fixture) == baseline[FIXTURE])

        ok("case2: the chain is green again after all injections",
           all(report.status == behavior.STATUS_PASS
               for report in verify().values()))
    finally:
        workspace.close()

    # ---------------- Case 3: 证据不足绝不 PASS ----------------
    print("=== Case 3: missing evidence never becomes PASS ===")
    frames = {"type": "simulation.advance_frames", "params": {"frames": 1}}
    absent = probe([frames],
                   [{"check": "health_bar.ratio", "target": "Host/MissingBar",
                     "equals": 1.0}],
                   behavior_id="absent_bar", tag="absent")
    ok("case3: a missing bar -> INSUFFICIENT / check_unavailable",
       absent.get("status") == "INSUFFICIENT"
       and absent.get("reason") == "check_unavailable",
       json.dumps(absent)[:300])
    wrong_type = probe([frames],
                       [{"check": "health_bar.ratio", "target": HEALTH,
                         "equals": 1.0}],
                       behavior_id="wrong_type", tag="wrong_type")
    ok("case3: a target without get_ratio (Health) -> INSUFFICIENT, not a guess",
       wrong_type.get("status") == "INSUFFICIENT"
       and wrong_type.get("reason") == "check_unavailable",
       json.dumps({key: wrong_type.get(key)
                   for key in ("status", "reason", "checks")})[:300])
    unmet = probe([frames],
                  [{"check": "health_bar.ratio", "target": BAR, "equals": 0.5}],
                  preconditions=[{"check": "health.current", "target": HEALTH,
                                  "equals": 10},
                                 {"check": "health_bar.ratio", "target": BAR,
                                  "equals": 0.5}],
                  behavior_id="unmet", tag="unmet")
    ok("case3: an unmet precondition -> INSUFFICIENT / precondition_unmet",
       unmet.get("status") == "INSUFFICIENT"
       and unmet.get("reason") == "precondition_unmet",
       json.dumps(unmet)[:300])
    # ---------------- Case 4: 重放不一致 ----------------
    print("=== Case 4: inconsistent replays are INSUFFICIENT ===")
    contract = [item for item in contracts if item["behavior"] == DAMAGE][0]

    def drifting_runner(attempt, project_root="", timeout_s=60, godot=""):
        observation = behavior.run_probe(attempt, project_root or PROJECT_ROOT,
                                         godot or _godot, timeout_s)
        payload = observation.get("result")
        if attempt.get("replay_index") == 2 and isinstance(payload, dict):
            payload = json.loads(json.dumps(payload))
            checks = payload.get("checks") or []
            if checks:
                checks[0]["observed"] = 0.61
            observation["result"] = payload
        return observation

    report = behavior.verify_contract(contract, PROJECT_ROOT, _godot, replay=2,
                                      runner=drifting_runner)
    ok("case4: divergent replays -> INSUFFICIENT / replay_inconsistent",
       report.status == behavior.STATUS_INSUFFICIENT
       and report.reason == "replay_inconsistent" and report.replay_count == 2,
       json.dumps(report.to_dict())[:300])
    ok("case4: both replays are kept in the evidence",
       len(report.runs) == 2
       and report.runs[1].get("checks")[0].get("observed") == 0.61)

    # ---------------- Case 5: 契约无效 ----------------
    print("=== Case 5: invalid contracts never reach Godot ===")
    damage = {"type": "health.take_damage", "target": HEALTH, "params": {"amount": 4}}
    invalid_case("window_zero",
                 {"id": "x", "actions": [damage],
                  "expected": [{"check": "health_bar.ratio", "target": BAR,
                                "equals": 0.6}], "window_frames": 0},
                 "window_frames must be")
    invalid_case("tolerance_without_equals",
                 {"id": "x", "actions": [damage],
                  "expected": [{"check": "health_bar.ratio", "target": BAR,
                                "tolerance": 0.1}], "window_frames": 5},
                 "tolerance requires equals")
    invalid_case("min_greater_than_max",
                 {"id": "x", "actions": [damage],
                  "expected": [{"check": "health_bar.ratio", "target": BAR,
                                "min": 0.9, "max": 0.1}], "window_frames": 5},
                 "must be <=")
    invalid_case("unknown_param",
                 {"id": "x", "actions": [damage],
                  "expected": [{"check": "health_bar.ratio", "target": BAR,
                                "equals": 0.6, "count": 1}], "window_frames": 5},
                 "count")
    invalid_case("wrong_equals_type",
                 {"id": "x", "actions": [damage],
                  "expected": [{"check": "health_bar.ratio", "target": BAR,
                                "equals": "full"}], "window_frames": 5},
                 "equals")
    invalid_case("scene_escape",
                 {"id": "x", "scene": "../health_bar/../../escape.tscn",
                  "actions": [damage],
                  "expected": [{"check": "health_bar.ratio", "target": BAR,
                                "equals": 0.6}], "window_frames": 5},
                 "relative path inside")

    # ---------------- Case 6: CLI 与恢复 ----------------
    print("=== Case 6: the CLI fails on a real defect and copies are restored ===")
    copy_root = os.path.join(_tempdir, "cli", "Features")
    shutil.copytree(FEATURES, copy_root)
    cli_script = os.path.join(copy_root, FEATURE, "health_bar.gd")
    with open(cli_script, "rb") as handle:
        cli_original = handle.read()
    write_text(cli_script, cli_original.decode("utf-8").replace(
        ratio_call, "\treturn 1.0\n", 1))
    proc = subprocess.run([sys.executable, CLI, "--feature", FEATURE,
                           "--features-dir", copy_root], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=900,
                          stdin=subprocess.DEVNULL, cwd=PROJECT_ROOT)
    ok("case6: the CLI exits 1 for a bar stuck at full",
       proc.returncode == 1 and "MISMATCH" in (proc.stdout or ""),
       "exit=%s out=%s" % (proc.returncode, (proc.stdout or "")[-300:]))
    ok("case6: the CLI names the damage contract, not some unrelated failure",
       DAMAGE in (proc.stdout or "") and "MISMATCH" in (proc.stdout or ""),
       (proc.stdout or "")[-400:])
    with open(cli_script, "wb") as handle:
        handle.write(cli_original)
    ok("case6: the CLI fixture copy is restored byte-for-byte",
       sha256(cli_script) == baseline[SCRIPT])

    ok("case6: repository Feature files are untouched",
       all(sha256(os.path.join(PROJECT_ROOT, path)) == digest
           for path, digest in baseline.items()))
    ok("case6: the behaviour manifest still matches its protocol",
       behavior_protocol.check_manifest(behavior_protocol.load_protocol()) == [])


if __name__ == "__main__":
    sys.exit(main())
