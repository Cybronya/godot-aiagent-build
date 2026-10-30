#!/usr/bin/env python3
"""Health 行为证据测试（Phase 1.51）

Phase 1.51 之前 `health` 有 3 条运行时行为契约（`damage` / `heal_clamped` / `death`），
但**没有任何针对本 Feature 自身的缺陷注入**：于是"契约存在"与"契约能拒绝错误实现"
这两件事从未被区分过。名字像测试、内容只证明正常路径，正是本阶段要拆开的东西。

本测试给出四类结论：

    Case 1  正向证据：5 条行为 PASS、2/2 重放一致、真实动作、观测值可推导、未用夹具、
            且观测窗口没有靠"等到对为止"（waited_frames = 0）
    Case 2  9 类真实缺陷注入（隔离副本，逐字节恢复）。其中 8 类被契约检出，并且逐条
            证明失败落在**正确的行为层面**（state_mismatch 还是 signal_mismatch），
            同时给出"相邻契约仍通过"的分辨力证据；第 9 类**不被任何契约检出**，
            如实记录为覆盖缺口，绝不当成通过。
    Case 3  证据不足：观测目标缺失 / 前置条件不满足 -> INSUFFICIENT，绝不 PASS；
            现象不成立（没死却断言 died）-> MISMATCH，而不是 PASS
    Case 4  重放不一致 -> INSUFFICIENT / replay_inconsistent
    Case 5  契约无效（窗口 0 / 伤害量越界 / 类型错误 / 未知检查 / 场景越界）-> INVALID，
            不启动 Godot。伤害量 0 与负数**无法表达**：协议把动作参数域声明为 1..100，
            这正是"0/负数输入被忽略"这条行为在行为证据层不可覆盖的原因（见审计报告）。
    Case 6  CLI 对真实缺陷返回 1、并指名被新契约捕获；副本逐字节恢复；仓库哈希不变；
            manifest 未漂移

用法:
    python .ai/tools/scene_composer/tests/test_health_behavior.py
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

FEATURE = "health"
ENTRY_SCENE = "res://Features/health/Health.tscn"
SCRIPT = os.path.join("Features", FEATURE, "health.gd")
TEMPLATE = os.path.join("Features", FEATURE, "template.yaml")

DAMAGE = "damage"
HEAL_CLAMPED = "heal_clamped"
DEATH = "death"
OVERKILL = "overkill_clamps_at_zero"
POST_DEATH = "post_death_guard"
LEGACY = (DAMAGE, HEAL_CLAMPED, DEATH)
ADDED = (OVERKILL, POST_DEATH)
BEHAVIORS = LEGACY + ADDED

TARGET = "."

# ---- 缺陷注入锚点（health.gd 里的唯一片断；锚点不唯一则测试直接报错，不静默跳过） ----
DAMAGE_LINE = "\t_current_health = max(_current_health - amount, 0)\n"
HEAL_LINE = "\t_current_health = min(_current_health + amount, max_health)\n"
EMIT_LINE = "\thealth_changed.emit(_current_health, amount)\n"
DAMAGE_BODY = DAMAGE_LINE + EMIT_LINE
HEAL_BODY = HEAL_LINE + EMIT_LINE
DEATH_BODY = "\t\t_is_dead = true\n\t\tdied.emit()\n"
# Phase 1.52 给 Health 加了无敌门（默认关），take_damage 守卫行多了一项；
# 锚点跟着真实实现走，注入时保留无敌门、只摘死亡守卫，用例语义不变。
TAKE_GUARD = "func take_damage(amount: int) -> void:\n\tif _is_dead or _invulnerable or amount <= 0:\n"
TAKE_GUARD_MINUS_DEATH = "func take_damage(amount: int) -> void:\n\tif _invulnerable or amount <= 0:\n"
READY_BODY = "func _ready() -> void:\n\t_current_health = max_health\n"


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


def observed(report, check_name: str, target: str = "") -> object:
    for check in report.actual if report else []:
        if check.get("check") == check_name and (not target
                                                 or check.get("target") == target):
            return check.get("observed")
    return None


def by_behavior(reports) -> dict:
    return {report.behavior: report for report in reports}


def detail_of(report) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False)[:300] if report else "missing"


def probe(actions, expected, window_frames=5, preconditions=None,
          behavior_id="case", tag="", project="", scene=ENTRY_SCENE):
    contract = {"feature": FEATURE, "behavior": behavior_id,
                "run_id": "health-%s-%s" % (behavior_id, tag or behavior_id),
                "replay_index": 1, "window_frames": window_frames, "scene": scene,
                "actions": actions, "preconditions": preconditions or [],
                "expected": expected}
    observation = behavior.run_probe(contract, project or PROJECT_ROOT, _godot,
                                     timeout_s=60)
    return observation.get("result") or {}


def build_feature(name: str, behavior_block):
    features = os.path.join(_tempdir, "contracts")
    directory = os.path.join(features, name)
    body = yaml.safe_dump(behavior_block, allow_unicode=True, sort_keys=False)
    write_text(os.path.join(directory, "template.yaml"),
               "feature:\n  id: %s\nscene:\n  source: Probe.tscn\nbehavior:\n%s"
               % (name, textwrap.indent(body, "  ")))
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
        print("SKIP: godot executable not found; health behaviour cannot be verified")
        return 1
    os.makedirs(os.path.join(DOTAI, "tmp"), exist_ok=True)
    _tempdir = tempfile.mkdtemp(prefix="health_behavior_", dir=os.path.join(DOTAI, "tmp"))
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
    print("PASS: all health behaviour checks passed")
    return 0


def run_cases() -> None:
    protocol = behavior_protocol.load_protocol()

    # ---------------- Case 1: 正向证据 ----------------
    print("=== Case 1: real Health updates are proven, not assumed ===")
    contracts, _ = behavior.build_contracts(FEATURE, FEATURES)
    ok("case1: five behaviors are declared in declaration order",
       [contract["behavior"] for contract in contracts] == list(BEHAVIORS),
       str([contract["behavior"] for contract in contracts]))
    ok("case1: the two Phase 1.51 behaviors are the only additions",
       set(BEHAVIORS) - set(LEGACY) == set(ADDED), str(BEHAVIORS))
    ok("case1: every behavior observes the entry scene (Health.tscn / max_health 5)",
       {contract["scene"] for contract in contracts} == {ENTRY_SCENE}
       and all(contract["window_frames"] == 10 for contract in contracts),
       str(sorted({contract["scene"] for contract in contracts})))
    # 验证 Health 契约依赖的能力与其权限边界，而非锁住整个共享协议的计数快照。
    # 新增无关 Feature 能力时，只要定义有效且 manifest 同步，不应使 Health 测试失效。
    health_actions = {"health.take_damage", "health.heal"}
    health_observations = {"health.current", "health.is_dead"}
    health_signals = {"health.health_changed", "health.died"}
    health_properties = {name for name, spec in protocol.properties.items()
                        if spec.get("class") == "Health"}
    ok("case1: the protocol contains the Health actions used by these contracts",
       health_actions <= set(protocol.actions), str(sorted(protocol.actions)))
    ok("case1: the protocol contains the Health observations used by these contracts",
       health_observations <= set(protocol.observations), str(sorted(protocol.observations)))
    ok("case1: the protocol contains the Health signals used by these contracts",
       health_signals <= set(protocol.signals), str(sorted(protocol.signals)))
    ok("case1: Health protocol exposes no writable properties",
       not health_properties, str(sorted(health_properties)))
    ok("case1: the observations it relies on are declared and read-only",
       protocol.observation("health.current")["result"]["type"] == "int"
       and protocol.observation("health.is_dead")["result"]["type"] == "bool"
       and protocol.observation("health.current")["implemented"] is True
       and protocol.observation("health.is_dead")["implemented"] is True,
       str((protocol.observation("health.current"),
            protocol.observation("health.is_dead"))))
    # 这是一条**缺口的事实记录**，不是断言"应该如此"：协议没有健康相关的可写属性，
    # 所以「max_health 配置被忽略」在行为证据层无法用夹具表达（见 Case 2f）。
    ok("case1: Health exposes no writable property in the protocol",
       "health.max_health" not in protocol.properties,
       str(sorted(protocol.properties)))

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
               detail_of(report))
            ok("case1: %s executed the real action (no fixture)" % name,
               report is not None and report.action_executed
               and all(record.get("executed") is True
                       for record in (report.runs[0].get("actions") or []))
               and not any(record.get("fixture") for record
                           in (report.runs[0].get("actions") or [])),
               json.dumps(report.runs[0].get("actions") if report else None)[:300])
            ok("case1: %s needed no window wait (synchronous)" % name,
               report is not None and int(report.runs[0].get("waited_frames") or 0) == 0,
               str(report.runs[0].get("waited_frames") if report else None))

        ok("case1: damage 5 - 4 = 1 with exactly one health_changed event",
           observed(found.get(DAMAGE), "health.current", TARGET) == 1
           and observed(found.get(DAMAGE), "signal", TARGET) == 1,
           detail_of(found.get(DAMAGE)))
        ok("case1: heal 99 from 1 clamps to max_health 5 (two events)",
           observed(found.get(HEAL_CLAMPED), "health.current", TARGET) == 5
           and observed(found.get(HEAL_CLAMPED), "signal", TARGET) == 2,
           detail_of(found.get(HEAL_CLAMPED)))
        ok("case1: lethal damage reaches 0 and reports death",
           observed(found.get(DEATH), "health.current", TARGET) == 0
           and observed(found.get(DEATH), "health.is_dead", TARGET) is True
           and observed(found.get(DEATH), "signal", TARGET) == 1,
           detail_of(found.get(DEATH)))
        ok("case1: 100 overkill damage still lands on 0 (not negative)",
           observed(found.get(OVERKILL), "health.current", TARGET) == 0
           and observed(found.get(OVERKILL), "health.is_dead", TARGET) is True,
           detail_of(found.get(OVERKILL)))
        ok("case1: damage and heal after death change nothing",
           observed(found.get(POST_DEATH), "health.current", TARGET) == 0
           and observed(found.get(POST_DEATH), "signal", TARGET) == 1,
           detail_of(found.get(POST_DEATH)))

        # ---------------- Case 2: 真实缺陷 ----------------
        print("=== Case 2: nine injected defects, each judged at the right level ===")
        script = os.path.join(workspace.project, SCRIPT)
        baseline_script = sha256(script)

        def verify_all() -> dict:
            return by_behavior(behavior.verify_feature(
                FEATURE, FEATURES, workspace.project, _godot, replay=1,
                workspace=workspace))

        def injection(label, old, new, broken, intact):
            """注入 -> 运行 -> 恢复 -> 逐条断言（含"哪一层失败"与"相邻契约仍通过"）。"""
            with open(script, "rb") as handle:
                original = handle.read()
            text = original.decode("utf-8")
            if text.count(old) != 1:
                raise AssertionError("patch anchor not unique/missing in health.gd: %r"
                                     % old)
            write_text(script, text.replace(old, new, 1))
            try:
                reports = verify_all()
            finally:
                with open(script, "wb") as handle:
                    handle.write(original)
            for name in sorted(broken):
                report = reports.get(name)
                ok("case2: %s -> %s MISMATCH / %s" % (label, name, broken[name]),
                   report is not None and report.status == behavior.STATUS_MISMATCH
                   and report.reason == broken[name], detail_of(report))
            for name in intact:
                report = reports.get(name)
                ok("case2: %s leaves %s passing (this is the discriminating power)"
                   % (label, name),
                   report is not None and report.status == behavior.STATUS_PASS,
                   detail_of(report))
            ok("case2: %s was restored byte-for-byte" % label,
               sha256(script) == baseline_script)
            return reports

        # 2a 数值更新缺陷：扣血少扣 1（更新逻辑错，而不是"没更新"）。
        # post_death_guard 在这一注入下是**信号层**失败：第一次伤害只到 1 不致命，
        # 第二次才归零，于是终值仍是 0（下限钳到 0），只有 health_changed 多了一次
        # 能被看见。"哪一层失败"是实测结果，不是设计意图（首轮预测成 state 是错的）。
        injection("2a-bad-arithmetic", DAMAGE_LINE,
                  "\t_current_health = max(_current_health - amount + 1, 0)\n",
                  {DAMAGE: "state_mismatch", DEATH: "state_mismatch",
                   POST_DEATH: "signal_mismatch"},
                  [HEAL_CLAMPED, OVERKILL])

        # 2b 边界缺陷：治疗上限钳制被移除（当前值可以超过 max_health）。
        injection("2b-heal-no-clamp", HEAL_LINE,
                  "\t_current_health = _current_health + amount\n",
                  {HEAL_CLAMPED: "state_mismatch"},
                  [DAMAGE, DEATH, OVERKILL, POST_DEATH])

        # 2c 事件证据缺陷：扣血事件的参数顺序颠倒（数值仍对，事件是错的）。
        injection("2c-damage-args-swapped", DAMAGE_BODY,
                  DAMAGE_LINE + "\thealth_changed.emit(amount, _current_health)\n",
                  {DAMAGE: "signal_mismatch", OVERKILL: "signal_mismatch"},
                  [HEAL_CLAMPED, DEATH, POST_DEATH])

        # 2d 事件证据缺陷：治疗事件的参数错误（Phase 1.51 才补上的 last_args 才看得见）。
        injection("2d-heal-args-wrong", HEAL_BODY,
                  HEAL_LINE + "\thealth_changed.emit(_current_health, 0)\n",
                  {HEAL_CLAMPED: "signal_mismatch"},
                  [DAMAGE, DEATH, OVERKILL, POST_DEATH])

        # 2e 事件证据缺陷：died 每次死亡触发两次。
        injection("2e-died-twice", DEATH_BODY,
                  "\t\t_is_dead = true\n\t\tdied.emit()\n\t\tdied.emit()\n",
                  {DEATH: "signal_mismatch", POST_DEATH: "signal_mismatch"},
                  [DAMAGE, HEAL_CLAMPED, OVERKILL])

        # 2f 边界缺陷：伤害下限钳制被移除（生命值可以变负）。
        injection("2f-no-lower-clamp", DAMAGE_LINE,
                  "\t_current_health = _current_health - amount\n",
                  {OVERKILL: "state_mismatch"},
                  [DAMAGE, HEAL_CLAMPED, DEATH, POST_DEATH])

        # 2g 状态转换缺陷：take_damage 的死亡守卫被移除。
        # 同样只在**信号层**暴露：0 - 2 被下限钳回 0，终值不变，但 health_changed
        # 与 died 各多触发一次（died 就是在这里被抓到的）。
        injection("2g-take-damage-guard-gone", TAKE_GUARD,
                  TAKE_GUARD_MINUS_DEATH,
                  {POST_DEATH: "signal_mismatch"},
                  [DAMAGE, HEAL_CLAMPED, DEATH, OVERKILL])

        # 2h 状态转换缺陷：heal 的死亡守卫被移除（死亡的另一半）。
        # 这里终值确实变了（0 + 3 = 3），所以是**状态层**失败——与 2g 互补，
        # 合起来证明 post_death_guard 的两半都有观测后果。
        injection("2h-heal-guard-gone",
                  "func heal(amount: int) -> void:\n\tif _is_dead or amount <= 0:\n",
                  "func heal(amount: int) -> void:\n\tif amount <= 0:\n",
                  {POST_DEATH: "state_mismatch"},
                  [DAMAGE, HEAL_CLAMPED, DEATH, OVERKILL])

        # 2i **不被检出**：把 _ready() 的初始化硬编码成 5，忽略 max_health 配置。
        # 仓库里没有任何契约在 max_health != 5 的场景上运行，因此这条缺陷对全部
        # 5 条契约都不可见。如实记录为覆盖缺口（不是"通过"，也不是"已验证"）。
        reports = injection("2i-max-health-ignored", READY_BODY,
                            "func _ready() -> void:\n\t_current_health = 5\n",
                            {}, list(BEHAVIORS))
        ok("case2: 2i is a REAL gap: every contract still passes on the hardcoded "
           "initialiser (none of them runs a scene whose max_health is not 5)",
           all(reports.get(name).status == behavior.STATUS_PASS
               for name in BEHAVIORS),
           str({name: reports.get(name).status for name in BEHAVIORS}))

        ok("case2: the chain is green again after all incidents",
           all(report.status == behavior.STATUS_PASS for report in verify_all().values()))
        ok("case2: repository health.gd was never touched by any injection",
           sha256(os.path.join(PROJECT_ROOT, SCRIPT)) == baseline_script)
    finally:
        workspace.close()

    # ---------------- Case 3: 证据不足绝不 PASS ----------------
    print("=== Case 3: missing evidence never becomes PASS ===")
    absent = probe([{"type": "health.take_damage", "target": TARGET,
                     "params": {"amount": 4}}],
                   [{"check": "health.current", "target": "Missing", "equals": 1}],
                   behavior_id="absent", tag="absent")
    ok("case3: a missing observation target -> INSUFFICIENT / check_unavailable",
       absent.get("status") == "INSUFFICIENT"
       and absent.get("reason") == "check_unavailable",
       json.dumps(absent)[:300])
    unmet = probe([{"type": "health.take_damage", "target": TARGET,
                    "params": {"amount": 4}}],
                  [{"check": "health.current", "target": TARGET, "equals": 1}],
                  preconditions=[{"check": "health.current", "target": TARGET,
                                  "equals": 4}],
                  behavior_id="unmet", tag="unmet")
    ok("case3: an unmet precondition -> INSUFFICIENT / precondition_unmet",
       unmet.get("status") == "INSUFFICIENT"
       and unmet.get("reason") == "precondition_unmet",
       json.dumps(unmet)[:300])
    ok("case3: the action was not executed when the precondition failed",
       unmet.get("action_executed") is False,
       str(unmet.get("action_executed")))
    # 现象不成立（没死却断言 died 恰好 1 次）必须是 MISMATCH，不能是 PASS。
    never = probe([{"type": "health.take_damage", "target": TARGET,
                    "params": {"amount": 1}}],
                  [{"check": "signal", "entry": "health.died", "target": TARGET,
                    "count": 1}],
                  behavior_id="never_died", tag="never_died")
    ok("case3: a death event that never happens -> MISMATCH, not PASS",
       never.get("status") == "MISMATCH" and never.get("reason") == "signal_mismatch",
       json.dumps(never)[:300])

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
                checks[0]["observed"] = 2
            observation["result"] = payload
        return observation

    report = behavior.verify_contract(contract, PROJECT_ROOT, _godot, replay=2,
                                      runner=drifting_runner)
    ok("case4: divergent replays -> INSUFFICIENT / replay_inconsistent",
       report.status == behavior.STATUS_INSUFFICIENT
       and report.reason == "replay_inconsistent" and report.replay_count == 2,
       detail_of(report))
    ok("case4: both replays are kept in the evidence",
       len(report.runs) == 2
       and report.runs[1].get("checks")[0].get("observed") == 2,
       json.dumps([run.get("checks") for run in report.runs])[:300])

    # ---------------- Case 5: 契约无效 ----------------
    print("=== Case 5: invalid contracts never reach Godot ===")
    damage = {"type": "health.take_damage", "target": TARGET, "params": {"amount": 4}}
    current_one = {"check": "health.current", "target": TARGET, "equals": 1}
    invalid_case("window_zero",
                 {"id": "x", "actions": [damage], "expected": [current_one],
                  "window_frames": 0}, "window_frames must be")
    invalid_case("amount_zero",
                 {"id": "x", "actions": [{"type": "health.take_damage", "target": TARGET,
                                          "params": {"amount": 0}}],
                  "expected": [current_one], "window_frames": 10}, "amount")
    invalid_case("amount_negative",
                 {"id": "x", "actions": [{"type": "health.take_damage", "target": TARGET,
                                          "params": {"amount": -3}}],
                  "expected": [current_one], "window_frames": 10}, "amount")
    invalid_case("amount_above_max",
                 {"id": "x", "actions": [{"type": "health.take_damage", "target": TARGET,
                                          "params": {"amount": 101}}],
                  "expected": [current_one], "window_frames": 10}, "amount")
    invalid_case("amount_wrong_type",
                 {"id": "x", "actions": [{"type": "health.take_damage", "target": TARGET,
                                          "params": {"amount": "four"}}],
                  "expected": [current_one], "window_frames": 10}, "amount")
    invalid_case("unknown_check",
                 {"id": "x", "actions": [damage],
                  "expected": [{"check": "health.max", "target": TARGET, "equals": 5}],
                  "window_frames": 10}, "health.max")
    invalid_case("scene_escape",
                 {"id": "x", "scene": "../health/../../escape.tscn", "actions": [damage],
                  "expected": [current_one], "window_frames": 10},
                 "relative path inside")

    # ---------------- Case 6: CLI 与恢复 ----------------
    print("=== Case 6: the CLI fails on a real defect and copies are restored ===")
    copy_root = os.path.join(_tempdir, "cli", "Features")
    shutil.copytree(FEATURES, copy_root)
    cli_script = os.path.join(copy_root, FEATURE, "health.gd")
    with open(cli_script, "rb") as handle:
        cli_original = handle.read()
    cli_text = cli_original.decode("utf-8")
    if cli_text.count(DAMAGE_LINE) != 1:
        raise AssertionError("patch anchor not unique/missing in the CLI copy")
    write_text(cli_script, cli_text.replace(
        DAMAGE_LINE, "\t_current_health = _current_health - amount\n", 1))
    proc = subprocess.run([sys.executable, CLI, "--feature", FEATURE,
                           "--features-dir", copy_root], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=900,
                          stdin=subprocess.DEVNULL, cwd=PROJECT_ROOT)
    ok("case6: the CLI exits 1 when the damage floor clamp is gone",
       proc.returncode == 1 and "MISMATCH" in (proc.stdout or ""),
       "exit=%s out=%s" % (proc.returncode, (proc.stdout or "")[-300:]))
    ok("case6: the CLI names the Phase 1.51 contract that catches it",
       OVERKILL in (proc.stdout or "") and "MISMATCH" in (proc.stdout or ""),
       (proc.stdout or "")[-500:])
    # 计数用 CLI 自己的汇总行与此刻的 behavior 行，不用子串出现次数
    # （"STATE_MISMATCH" / "SIGNAL_MISMATCH" 都含有 "MISMATCH"，数子串会自欺）。
    lines = [line.strip() for line in (proc.stdout or "").splitlines()]
    flagged = [line for line in lines
               if line.startswith("health") and " MISMATCH" in line]
    ok("case6: exactly one behavior mismatches, and it is the Phase 1.51 one",
       "pass=4 mismatch=1" in (proc.stdout or "")
       and len(flagged) == 1 and OVERKILL in flagged[0],
       (proc.stdout or "")[-500:])
    with open(cli_script, "wb") as handle:
        handle.write(cli_original)
    ok("case6: the CLI fixture copy is restored byte-for-byte",
       sha256(cli_script) == baseline_script)

    ok("case6: repository Feature files are untouched",
       sha256(os.path.join(PROJECT_ROOT, SCRIPT)) == baseline_script
       and os.path.isfile(os.path.join(FEATURES, FEATURE, "Health.tscn"))
       and os.path.isfile(os.path.join(PROJECT_ROOT, TEMPLATE)))
    ok("case6: the behaviour manifest still matches its protocol",
       behavior_protocol.check_manifest(behavior_protocol.load_protocol()) == [])


if __name__ == "__main__":
    sys.exit(main())
