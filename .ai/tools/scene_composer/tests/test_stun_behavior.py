#!/usr/bin/env python3
"""眩晕行为证据测试（Phase 1.49）

`stun` 在 Phase 1.49 前只有 `Features/stun/test_stun.gd` 这一份**直接调用 API** 的
Godot 单元测试：它能证明方法语义，但绕过行为协议（没有受限动作、没有负向对照、
没有重放一致性，也无法证明「真实受击链 → 宿主真的停摆」）。

本测试证明协议足以表达并判别这条链：

    Case 1  正向证据：5 条行为 PASS、2/2 重放一致、观测值可追溯
    Case 2  真实缺陷（隔离副本）：物理停摆被移除 / 恢复被移除 / 治疗也触发 /
            死亡守卫被移除 / 幂等广播失效 / 受击订阅未配置 —— 各自只打穿对应契约
    Case 3  观测缺口：目标不存在 → INSUFFICIENT；窗口短于现象 → MISMATCH，
            同一条契约给足窗口则 PASS（证明失败原因确实来自窗口）
    Case 4  重放不一致 → INSUFFICIENT / replay_inconsistent
    Case 5  契约无效（窗口 0 / 未登记信号 / 场景越界）→ INVALID，不启动 Godot
    Case 6  CLI 对真实缺陷返回 1；隔离副本逐字节恢复；仓库文件哈希不变

触发只走 `health.take_damage`（真实 health_changed → stun_on_hit 订阅），
**不**调用 `stun()` 方法；可观测证据是宿主位移（真实 CharacterBody2D 物理）
与 `stunned(bool)` 的跨越广播。

用法:
    python .ai/tools/scene_composer/tests/test_stun_behavior.py
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

FEATURE = "stun"
FIXTURE_SCENE = "res://Features/stun/StunFixture.tscn"
ENTRY_SCENE = "res://Features/stun/Stun.tscn"
SCRIPT = os.path.join("Features", FEATURE, "stun.gd")
FIXTURE = os.path.join("Features", FEATURE, "StunFixture.tscn")
TEMPLATE = os.path.join("Features", FEATURE, "template.yaml")

FREEZE = "hit_stuns_and_freezes_host"
RESUME = "stun_expires_and_host_resumes"
HEAL = "heal_does_not_stun"
DEATH = "death_guard_rejects_stun"
REENTRY = "reentry_extends_without_rebroadcast"
BEHAVIORS = (FREEZE, RESUME, HEAL, DEATH, REENTRY)


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
                "run_id": "stun-%s-%s" % (behavior_id, tag or behavior_id),
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
        print("SKIP: godot executable not found; stun behaviour cannot be verified")
        return 1
    os.makedirs(os.path.join(DOTAI, "tmp"), exist_ok=True)
    _tempdir = tempfile.mkdtemp(prefix="stun_behavior_", dir=os.path.join(DOTAI, "tmp"))
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
    print("PASS: all stun behaviour checks passed")
    return 0


def run_cases() -> None:
    protocol = behavior_protocol.load_protocol()

    # ---------------- Case 1: 正向证据 ----------------
    print("=== Case 1: stun is proven by real physics and real hit events ===")
    contracts, _ = behavior.build_contracts(FEATURE, FEATURES)
    ok("case1: five behaviors are declared with the dedicated fixture",
       [contract["behavior"] for contract in contracts] == list(BEHAVIORS)
       and all(contract["scene"] == FIXTURE_SCENE for contract in contracts),
       str([(contract["behavior"], contract["scene"]) for contract in contracts]))
    ok("case1: the entry scene stays untouched by behaviour evidence",
       all(contract["scene"] != ENTRY_SCENE for contract in contracts)
       and os.path.isfile(os.path.join(FEATURES, FEATURE, "Stun.tscn")))
    ok("case1: the stunned signal is registered in the shared protocol",
       protocol.signal("stun.stunned") == {"signal": "stunned", "args": ["bool"]},
       str(protocol.signal("stun.stunned")))

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
            ok("case1: %s executed the real hit action" % name,
               report is not None and report.action_executed
               and all(record.get("executed") is True
                       for record in (report.runs[0].get("actions") or [])),
               json.dumps(report.runs[0].get("actions") if report else None)[:300])
            ok("case1: %s used no fixture action" % name,
               report is not None
               and not any(record.get("fixture") for record
                           in (report.runs[0].get("actions") or [])),
               json.dumps(report.runs[0].get("actions") if report else None)[:300])

        freeze = found.get(FREEZE)
        ok("case1: the hit froze the host within one frame (3.7 px, not 73 px)",
           isinstance(observed(freeze, "node2d.displacement", "Host"), float)
           and observed(freeze, "node2d.displacement", "Host") <= 8.0,
           str(observed(freeze, "node2d.displacement", "Host")))
        ok("case1: the hit cost 1 HP and broadcast exactly one true",
           observed(freeze, "health.current", "Host/Health") == 9
           and observed(freeze, "signal", "Host/Stun") == 1,
           json.dumps([{key: check.get(key) for key in ("check", "observed")}
                       for check in (freeze.actual if freeze else [])]))

        resume = found.get(RESUME)
        resume_x = observed(resume, "node2d.displacement", "Host")
        ok("case1: after 0.4s the host moves again (77 px: 24 frozen + 21 moving)",
           isinstance(resume_x, float) and 60.0 <= resume_x <= 90.0, str(resume_x))
        ok("case1: recovery broadcast exactly one false",
           observed(resume, "signal", "Host/Stun") == 2,
           str(observed(resume, "signal", "Host/Stun")))
        heal_x = observed(found.get(HEAL), "node2d.displacement", "Host")
        ok("case1: an un-stunned host covers 88 px in the same 24 frames",
           isinstance(heal_x, float) and 87.5 <= heal_x <= 88.5, str(heal_x))
        ok("case1: healing emits health_changed but never stuns",
           observed(found.get(HEAL), "signal", "Host/Stun") == 0
           and observed(found.get(HEAL), "health.current", "Host/Health") == 10)
        ok("case1: a lethal hit never stuns (death guard) and does not pause physics",
           observed(found.get(DEATH), "health.is_dead", "Host/Health") is True
           and observed(found.get(DEATH), "signal", "Host/Stun") == 0
           and (observed(found.get(DEATH), "node2d.displacement", "Host") or 0) >= 60.0,
           json.dumps([{key: check.get(key) for key in ("check", "observed")}
                       for check in (found.get(DEATH).actual if found.get(DEATH) else [])]))
        ok("case1: a second hit during stun extends without a second true",
           observed(found.get(REENTRY), "signal", "Host/Stun") == 1
           and observed(found.get(REENTRY), "health.current", "Host/Health") == 8,
           json.dumps([{key: check.get(key) for key in ("check", "observed")}
                       for check in (found.get(REENTRY).actual
                                     if found.get(REENTRY) else [])]))

        ok("case1: no behaviour needed the window to expire",
           all(int(report.runs[0].get("waited_frames") or 0) == 0
               for report in reports),
           str({report.behavior: report.runs[0].get("waited_frames")
                for report in reports}))

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

        # 2a 物理停摆被移除：受击后宿主照常移动。
        original = patch(script, "\t\t_host.set_physics_process(false)\n",
                         "\t\tpass\n")
        reports = verify()
        restore(script, original)
        broken = reports.get(FREEZE)
        broken_x = observed(broken, "node2d.displacement", "Host")
        ok("case2: removing the physics pause -> MISMATCH / state_mismatch",
           broken is not None and broken.status == behavior.STATUS_MISMATCH
           and broken.reason == "state_mismatch",
           json.dumps(broken.to_dict())[:300] if broken else "missing")
        ok("case2: the host keeps moving (≈73 px) instead of freezing",
           isinstance(broken_x, float) and broken_x > 60.0, str(broken_x))
        # 计数不固定为 1：位移断言失败后探针会跑满 5 帧窗口，0.4 s 的眩晕可能在窗口内到期
        # 而多出一个 false。所以这里只要求「true 真的发出过」，失败点因此是停摆本身。
        ok("case2: the signal is still emitted, so the failure is the freeze itself",
           (observed(broken, "signal", "Host/Stun") or 0) >= 1,
           str(observed(broken, "signal", "Host/Stun")))
        ok("case2: the heal control still passes while the pause is removed",
           reports.get(HEAL).status == behavior.STATUS_PASS,
           json.dumps(reports.get(HEAL).to_dict())[:300])
        ok("case2: the paused-physics script is restored byte-for-byte",
           sha256(script) == baseline[SCRIPT])

        # 2b 恢复被移除：宿主永远停摆。
        original = patch(script, "\t\t\t_host.set_physics_process(true)\n",
                         "\t\t\tpass\n")
        reports = verify()
        restore(script, original)
        stuck = reports.get(RESUME)
        stuck_x = observed(stuck, "node2d.displacement", "Host")
        ok("case2: removing the recovery -> MISMATCH at the resume contract",
           stuck is not None and stuck.status == behavior.STATUS_MISMATCH
           and stuck.reason == "state_mismatch",
           json.dumps(stuck.to_dict())[:300] if stuck else "missing")
        # 注入只删掉了恢复物理的调用，`stunned.emit(false)` 仍在：所以宿主停住了，
        # 但 false 边沿照样发出（2 次）——这正是「状态转移与物理恢复是两件事」的证据。
        ok("case2: the host stays frozen although the false edge is still emitted",
           isinstance(stuck_x, float) and stuck_x <= 8.0
           and observed(stuck, "signal", "Host/Stun") == 2,
           "x=%s events=%s" % (stuck_x, observed(stuck, "signal", "Host/Stun")))
        ok("case2: the freeze contract still passes without recovery",
           reports.get(FREEZE).status == behavior.STATUS_PASS,
           json.dumps(reports.get(FREEZE).to_dict())[:300])
        ok("case2: the recovery-patched script is restored byte-for-byte",
           sha256(script) == baseline[SCRIPT])

        # 2c 受击判定被写成「任何 health_changed 都算受击」：治疗也眩晕。
        original = patch(script, "\tvar damaged := current < _last_health\n",
                         "\tvar damaged := true\n")
        reports = verify()
        restore(script, original)
        healed = reports.get(HEAL)
        ok("case2: treating every health_changed as a hit -> heal contract MISMATCH",
           healed is not None and healed.status == behavior.STATUS_MISMATCH,
           json.dumps(healed.to_dict())[:300] if healed else "missing")
        # 0.4 s 眩晕在 24 帧的推进里会到期，所以不是完全冻结，而是「大部分时间停摆」：
        # 22 px 远小于 88 px。这就是「治疗被当成受击」的可观测红牌。
        # 断言名只用 GBK 可编码字符：Windows 控制台默认 GBK 时，打印 ≪ 会抛
        # UnicodeEncodeError，让一条通过的测试以退出码 1 结束（Phase 1.50 实测）。
        ok("case2: healing now freezes the host for most of the window (far below 88 px)",
           (observed(healed, "node2d.displacement", "Host") or 99.0) < 45.0
           and (observed(healed, "signal", "Host/Stun") or 0) >= 1,
           "x=%s events=%s" % (observed(healed, "node2d.displacement", "Host"),
                               observed(healed, "signal", "Host/Stun")))
        ok("case2: the real hit contract still passes",
           reports.get(FREEZE).status == behavior.STATUS_PASS,
           json.dumps(reports.get(FREEZE).to_dict())[:300])
        ok("case2: the damaged-check script is restored byte-for-byte",
           sha256(script) == baseline[SCRIPT])

        # 2d 死亡守卫被移除：击杀也会眩晕。
        original = patch(script,
                         "\tif _health != null and _health.is_dead():\n\t\treturn false\n",
                         "")
        reports = verify()
        restore(script, original)
        dead = reports.get(DEATH)
        ok("case2: removing the death guard -> MISMATCH at the death contract",
           dead is not None and dead.status == behavior.STATUS_MISMATCH
           and dead.reason == "state_mismatch",
           json.dumps(dead.to_dict())[:300] if dead else "missing")
        ok("case2: the dead host is frozen instead of being ignored",
           (observed(dead, "node2d.displacement", "Host") or 99.0) <= 8.0
           and (observed(dead, "signal", "Host/Stun") or 0) >= 1,
           "x=%s events=%s" % (observed(dead, "node2d.displacement", "Host"),
                               observed(dead, "signal", "Host/Stun")))
        ok("case2: the live-hit contract still passes without the death guard",
           reports.get(FREEZE).status == behavior.STATUS_PASS,
           json.dumps(reports.get(FREEZE).to_dict())[:300])
        ok("case2: the death-guard script is restored byte-for-byte",
           sha256(script) == baseline[SCRIPT])

        # 2e 幂等广播失效：眩晕中再次受击重复广播 true。
        original = patch(script, "\tif _remaining <= 0.0:\n\t\t_host.set_physics_process(false)\n",
                         "\tif true:\n\t\t_host.set_physics_process(false)\n")
        reports = verify()
        restore(script, original)
        reentry = reports.get(REENTRY)
        ok("case2: a re-broadcast on re-entry -> re-entry contract MISMATCH",
           reentry is not None and reentry.status == behavior.STATUS_MISMATCH,
           json.dumps(reentry.to_dict())[:300] if reentry else "missing")
        ok("case2: two true broadcasts are observed where one is allowed",
           observed(reentry, "signal", "Host/Stun") == 2,
           str(observed(reentry, "signal", "Host/Stun")))
        ok("case2: the single-hit and resume contracts still pass",
           reports.get(FREEZE).status == behavior.STATUS_PASS
           and reports.get(RESUME).status == behavior.STATUS_PASS,
           json.dumps([reports.get(FREEZE).status, reports.get(RESUME).status]))
        ok("case2: the idempotency-patched script is restored byte-for-byte",
           sha256(script) == baseline[SCRIPT])

        # 2f 组合前置不成立：stun_on_hit 未配置 → 受击链根本没接上。
        original = patch(fixture, "stun_on_hit = true", "stun_on_hit = false")
        reports = verify()
        restore(fixture, original)
        silent = reports.get(FREEZE)
        # 死亡契约本身断言的是「没有眩晕」，所以触发链断开时它仍然成立——这是 absence 型
        # 契约的固有弱项，由 freeze/resume/reentry 三条正向契约负责抓：
        ok("case2: an unconfigured hit trigger -> MISMATCH on the positive contracts",
           all(reports.get(name).status == behavior.STATUS_MISMATCH
               for name in (FREEZE, RESUME, REENTRY)),
           str({name: reports.get(name).status
                for name in (FREEZE, RESUME, REENTRY)}))
        ok("case2: the absence-only death contract cannot see the unwired trigger",
           reports.get(DEATH).status == behavior.STATUS_PASS,
           json.dumps(reports.get(DEATH).to_dict())[:300])
        ok("case2: the host simply moves (≈73 px) and no stun is broadcast",
           (observed(silent, "node2d.displacement", "Host") or 0) > 60.0
           and observed(silent, "signal", "Host/Stun") == 0,
           "x=%s events=%s" % (observed(silent, "node2d.displacement", "Host"),
                               observed(silent, "signal", "Host/Stun")))
        ok("case2: the heal control still passes without a hit trigger",
           reports.get(HEAL).status == behavior.STATUS_PASS,
           json.dumps(reports.get(HEAL).to_dict())[:300])
        ok("case2: the fixture is restored byte-for-byte",
           sha256(fixture) == baseline[FIXTURE])

        ok("case2: the chain is green again after all injections",
           all(report.status == behavior.STATUS_PASS
               for report in verify().values()))
    finally:
        workspace.close()

    # ---------------- Case 3: 观测缺口 ----------------
    print("=== Case 3: missing evidence never becomes PASS ===")
    press = {"type": "input.press", "params": {"action": "move_right"}}
    damage = {"type": "health.take_damage", "target": "Host/Health",
              "params": {"amount": 1}}
    absent = probe([press, {"type": "simulation.advance_frames",
                            "params": {"frames": 1}}, damage],
                   [{"check": "signal", "target": "Host/MissingStun",
                     "entry": "stun.stunned", "count": 1}],
                   behavior_id="absent_stun", tag="absent")
    ok("case3: an unresolved signal target -> INSUFFICIENT / check_unavailable",
       absent.get("status") == "INSUFFICIENT"
       and absent.get("reason") == "check_unavailable",
       json.dumps(absent)[:300])

    short = probe([press, {"type": "simulation.advance_frames",
                           "params": {"frames": 1}}, damage],
                  [{"check": "node2d.displacement", "target": "Host",
                    "axis": "x", "min": 45.0}],
                  window_frames=3, behavior_id="short_window", tag="short")
    ok("case3: a 3-frame window cannot see a 0.4s stun expire -> MISMATCH",
       short.get("status") == "MISMATCH" and short.get("reason") == "state_mismatch"
       and short.get("waited_frames") == 3
       and (short.get("checks") or [{}])[0].get("observed", 99.0) <= 8.0,
       json.dumps({key: short.get(key) for key in ("status", "reason",
                                                   "waited_frames", "checks")})[:400])
    long_window = probe([press, {"type": "simulation.advance_frames",
                                 "params": {"frames": 1}}, damage],
                        [{"check": "node2d.displacement", "target": "Host",
                          "axis": "x", "min": 45.0}],
                        window_frames=50, behavior_id="long_window", tag="long")
    ok("case3: the same contract passes once the window covers the recovery",
       long_window.get("status") == "PASS"
       and (long_window.get("checks") or [{}])[0].get("observed", 0.0) > 45.0,
       json.dumps({key: long_window.get(key)
                   for key in ("status", "reason", "waited_frames",
                               "checks")})[:400])

    # ---------------- Case 4: 重放不一致 ----------------
    print("=== Case 4: inconsistent replays are INSUFFICIENT ===")
    contract = [item for item in contracts if item["behavior"] == FREEZE][0]

    def drifting_runner(attempt, project_root="", timeout_s=60, godot=""):
        observation = behavior.run_probe(attempt, project_root or PROJECT_ROOT,
                                         godot or _godot, timeout_s)
        payload = observation.get("result")
        if attempt.get("replay_index") == 2 and isinstance(payload, dict):
            payload = json.loads(json.dumps(payload))
            checks = payload.get("checks") or []
            if checks:
                checks[0]["observed"] = 999.0
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
       and report.runs[1].get("checks")[0].get("observed") == 999.0)

    # ---------------- Case 5: 契约无效 ----------------
    print("=== Case 5: invalid contracts never reach Godot ===")
    invalid_case("window_zero",
                 {"id": "x", "actions": [damage],
                  "expected": [{"check": "health.current", "target": "Host/Health",
                                "equals": 9}], "window_frames": 0},
                 "window_frames must be")
    invalid_case("unknown_signal",
                 {"id": "x", "actions": [damage],
                  "expected": [{"check": "signal", "target": "Host/Stun",
                                "entry": "stun.teleported", "count": 1}],
                  "window_frames": 5},
                 "stun.teleported")
    invalid_case("scene_escape",
                 {"id": "x", "scene": "../stun/../../escape.tscn",
                  "actions": [damage],
                  "expected": [{"check": "health.current", "target": "Host/Health",
                                "equals": 9}], "window_frames": 5},
                 "relative path inside")
    invalid_case("damage_without_amount",
                 {"id": "x",
                  "actions": [{"type": "health.take_damage", "target": "Host/Health"}],
                  "expected": [{"check": "health.current", "target": "Host/Health",
                                "equals": 9}], "window_frames": 5},
                 "amount")

    # ---------------- Case 6: CLI 与恢复 ----------------
    print("=== Case 6: the CLI fails on a real defect and copies are restored ===")
    copy_root = os.path.join(_tempdir, "cli", "Features")
    shutil.copytree(FEATURES, copy_root)
    cli_script = os.path.join(copy_root, FEATURE, "stun.gd")
    with open(cli_script, "rb") as handle:
        cli_original = handle.read()
    write_text(cli_script, cli_original.decode("utf-8").replace(
        "\t\t_host.set_physics_process(false)\n", "\t\tpass\n", 1))
    proc = subprocess.run([sys.executable, CLI, "--feature", FEATURE,
                           "--features-dir", copy_root], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=900,
                          stdin=subprocess.DEVNULL, cwd=PROJECT_ROOT)
    ok("case6: the CLI exits 1 for a removed physics pause",
       proc.returncode == 1 and "MISMATCH" in (proc.stdout or ""),
       "exit=%s out=%s" % (proc.returncode, (proc.stdout or "")[-300:]))
    ok("case6: the CLI names the freeze contract, not some unrelated failure",
       FREEZE in (proc.stdout or "") and "MISMATCH" in (proc.stdout or ""),
       (proc.stdout or "")[-400:])
    with open(cli_script, "wb") as handle:
        handle.write(cli_original)
    ok("case6: the CLI fixture copy is restored byte-for-byte",
       sha256(cli_script) == baseline[SCRIPT])

    ok("case6: repository Feature files are untouched",
       all(sha256(os.path.join(PROJECT_ROOT, path)) == digest
           for path, digest in baseline.items()),
       str({path: (digest, sha256(os.path.join(PROJECT_ROOT, path)))
            for path, digest in baseline.items()
            if digest != sha256(os.path.join(PROJECT_ROOT, path))}))
    ok("case6: the behaviour manifest still matches its protocol",
       behavior_protocol.check_manifest(behavior_protocol.load_protocol()) == [])


if __name__ == "__main__":
    sys.exit(main())
