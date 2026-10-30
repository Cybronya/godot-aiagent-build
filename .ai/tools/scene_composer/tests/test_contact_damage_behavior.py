#!/usr/bin/env python3
"""接触伤害行为证据测试（Phase 1.47）

`contact_damage` 没有公开方法与信号：唯一的行为入口是「真实物理重叠 + 物理帧上的
节拍结算」。因此本测试不补齐任何新能力，只证明既有协议足以表达并判别这类行为：

    Case 1  正向证据：damage_on_contact / no_damage_without_contact /
            damage_amount_is_respected 均 PASS，2/2 重放一致
    Case 2  真实缺陷（隔离副本）：伤害调用被移除 → MISMATCH；伤害量被硬编码
            → 只有「伤害量」契约失败；接触前置被删除 → 只有「无接触不伤害」失败
    Case 3  观测缺口：观察目标不存在 → INSUFFICIENT；窗口短于一个结算节拍 → MISMATCH
    Case 4  重放不一致 → INSUFFICIENT / replay_inconsistent（两次结果都保留）
    Case 5  契约无效（窗口 0 / 缺 group / 场景越界）→ INVALID，不启动 Godot
    Case 6  CLI 对真实缺陷返回非 0；注入副本与仓库文件按 SHA256 恢复

`@actor/Health` 由 `physics.overlap` 生成的真实 `CharacterBody2D` + 真实 Health.tscn
提供；信号监听在动作执行后补连（Phase 1.47 补上的 `@actor` 观测缺口）。
不使用 `physics.overlap` 的 `damage` 参数——那个参数会直接调用 take_damage，等于
替被测组件制造伤害结果。

用法:
    python .ai/tools/scene_composer/tests/test_contact_damage_behavior.py
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

FEATURE = "contact_damage"
FIXTURE_SCENE = "res://Features/contact_damage/ContactDamageFixture.tscn"
ENTRY_SCENE = "res://Features/contact_damage/ContactDamage.tscn"
BEHAVIORS = ("damage_on_contact", "no_damage_without_contact",
             "damage_amount_is_respected")


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


def overlap(target, group="players", health_max=5):
    return {"type": "physics.overlap", "target": target,
            "params": {"group": group, "health_max": health_max}}


def probe(actions, expected, window_frames=45, preconditions=None,
          behavior_id="case", tag="", project="", scene=FIXTURE_SCENE):
    contract = {"feature": FEATURE, "behavior": behavior_id,
                "run_id": "contact-%s-%s" % (behavior_id, tag or behavior_id),
                "replay_index": 1, "window_frames": window_frames, "scene": scene,
                "actions": actions, "preconditions": preconditions or [],
                "expected": expected}
    observation = behavior.run_probe(contract, project or PROJECT_ROOT, _godot,
                                     timeout_s=60)
    return observation.get("result") or {}


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


def invalid_case(label: str, behavior_block, needle: str, files=None) -> None:
    contracts, reports = build_feature(label, [behavior_block], files=files)
    detail = reports[0].detail if reports else "contract accepted"
    ok("case5: %s -> INVALID" % label,
       not contracts and bool(reports) and reports[0].status == behavior.STATUS_INVALID
       and needle in detail, detail)


def main() -> int:
    global _godot, _tempdir
    _godot = runtime_evidence.find_godot(PROJECT_ROOT)
    if not _godot:
        print("SKIP: godot executable not found; contact damage cannot be verified")
        return 1
    os.makedirs(os.path.join(DOTAI, "tmp"), exist_ok=True)
    _tempdir = tempfile.mkdtemp(prefix="contact_behavior_",
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
    print("PASS: all contact damage behavior checks passed")
    return 0


def run_cases() -> None:
    protocol = behavior_protocol.load_protocol()

    # ---------------- Case 1: 真实接触伤害证据 ----------------
    print("=== Case 1: contact damage is proven by real physics contact ===")
    workspace = behavior.BehaviorWorkspace(FEATURES, _godot)
    try:
        reports = behavior.verify_feature(FEATURE, FEATURES, FEATURES, _godot,
                                          replay=2, workspace=workspace)
        by_id = {report.behavior: report for report in reports}
        ok("case1: all three behaviors were checked", set(by_id) == set(BEHAVIORS),
           str(sorted(by_id)))
        for name in BEHAVIORS:
            report = by_id.get(name)
            ok("case1: %s PASS with two consistent replays" % name,
               report is not None and report.status == behavior.STATUS_PASS
               and report.replay_count == 2 and report.replay_consistent,
               json.dumps(report.to_dict())[:400] if report else "missing")
            ok("case1: %s executed the real physics.overlap action" % name,
               report is not None and report.action_executed
               and (report.runs[0].get("actions") or [{}])[0].get("executed") is True
               and not (report.runs[0].get("actions") or [{}])[0].get("fixture"),
               json.dumps(report.runs[0].get("actions") if report else None)[:300])

        damage = by_id.get("damage_on_contact")
        untouched = by_id.get("no_damage_without_contact")
        amount = by_id.get("damage_amount_is_respected")
        ok("case1: contact really costs 1 HP and emits exactly one event",
           damage is not None
           and [check.get("observed") for check in damage.actual] == [4, 1]
           and [check.get("expected") for check in damage.actual] == [4, 1],
           json.dumps([{k: c.get(k) for k in ("check", "observed", "expected")}
                       for c in (damage.actual if damage else [])]))
        ok("case1: the configured damage=3 instance takes 3 HP, not 1",
           amount is not None
           and [check.get("observed") for check in amount.actual] == [2, 1]
           and [check.get("expected") for check in amount.actual] == [2, 1],
           json.dumps([{k: c.get(k) for k in ("check", "observed", "expected")}
                       for c in (amount.actual if amount else [])]))
        ok("case1: without contact health stays 5 and no event is emitted",
           untouched is not None
           and [check.get("observed") for check in untouched.actual] == [5, 0],
           json.dumps([{k: c.get(k) for k in ("check", "observed", "expected")}
                       for c in (untouched.actual if untouched else [])]))
        # 时序：0.5s 节拍 = 30 帧；实测首次伤害在 24–25 帧被观测到，窗口 45 帧未耗尽。
        for name in ("damage_on_contact", "damage_amount_is_respected"):
            report = by_id.get(name)
            waited = report.runs[0].get("waited_frames") if report else None
            ok("case1: %s observed the first tick inside the window" % name,
               isinstance(waited, int) and 15 <= waited < 45
               and report.first_observed_frame == waited,
               "waited=%s first=%s" % (waited, getattr(report, "first_observed_frame", None)))
            window = report.window_frames if report else None
            ok("case1: %s did not run out of the frame budget" % name,
               window == 45 and protocol.frame_budget_errors(
                   (report.actions if report else []), window) == [],
               str(window))

        contracts, _ = behavior.build_contracts(FEATURE, FEATURES)
        ok("case1: every behavior uses the dedicated fixture scene",
           [contract["scene"] for contract in contracts]
           == [FIXTURE_SCENE, FIXTURE_SCENE, FIXTURE_SCENE],
           str([contract["scene"] for contract in contracts]))
        ok("case1: the entry scene is untouched by behavior evidence",
           all(contract["scene"] != ENTRY_SCENE for contract in contracts)
           and os.path.isfile(os.path.join(FEATURES, FEATURE, "ContactDamage.tscn")))

        # ---------------- Case 2: 真实缺陷 ----------------
        print("=== Case 2: real defects produce MISMATCH, not PASS ===")
        script_name = "contact_damage.gd"
        baseline = {
            "script": sha256(os.path.join(FEATURES, FEATURE, script_name)),
            "fixture": sha256(os.path.join(FEATURES, FEATURE, "ContactDamageFixture.tscn")),
            "template": sha256(os.path.join(FEATURES, FEATURE, "template.yaml")),
        }
        script = os.path.join(workspace.project, "Features", FEATURE, script_name)

        def verify_in_workspace():
            return {report.behavior: report
                    for report in behavior.verify_feature(
                        FEATURE, FEATURES, workspace.project, _godot,
                        replay=1, workspace=workspace)}

        def patch(old, new):
            with open(script, "rb") as handle:
                original = handle.read()
            text = original.decode("utf-8")
            if old not in text:
                raise AssertionError("patch anchor not found: %r" % old)
            write_text(script, text.replace(old, new, 1))
            return original

        def restore(original):
            with open(script, "wb") as handle:
                handle.write(original)

        def observed(report, index=0):
            checks = report.actual if report else []
            return checks[index].get("observed") if len(checks) > index else None

        muted = patch("\thealth.take_damage(damage)\n", "\tpass\n")
        reports = verify_in_workspace()
        ok("case2: a removed damage call -> MISMATCH / state_mismatch",
           reports["damage_on_contact"].status == behavior.STATUS_MISMATCH
           and reports["damage_on_contact"].reason == "state_mismatch"
           and observed(reports["damage_on_contact"]) == 5,
           json.dumps(reports["damage_on_contact"].to_dict())[:300])
        ok("case2: the no-contact control still passes while damage is muted",
           reports["no_damage_without_contact"].status == behavior.STATUS_PASS,
           json.dumps(reports["no_damage_without_contact"].to_dict())[:300])
        restore(muted)
        ok("case2: the muted-damage script is restored byte-for-byte",
           sha256(script) == baseline["script"])

        hardcoded = patch("\thealth.take_damage(damage)\n", "\thealth.take_damage(1)\n")
        reports = verify_in_workspace()
        # 5 - 1 = 4：生命值仍然"变了"，只有「伤害量必须是配置值」这条契约能抓到。
        ok("case2: a hardcoded damage of 1 -> only the amount contract fails",
           reports["damage_amount_is_respected"].status == behavior.STATUS_MISMATCH
           and observed(reports["damage_amount_is_respected"]) == 4
           and reports["damage_amount_is_respected"].expected[0].get("equals") == 2,
           json.dumps(reports["damage_amount_is_respected"].to_dict())[:300])
        ok("case2: the 1-damage contract still passes with hardcoded 1",
           reports["damage_on_contact"].status == behavior.STATUS_PASS,
           json.dumps(reports["damage_on_contact"].to_dict())[:300])
        restore(hardcoded)
        ok("case2: the hardcoded-amount script is restored byte-for-byte",
           sha256(script) == baseline["script"])

        contactless = patch(
            "\tfor body: Node2D in get_overlapping_bodies():\n",
            "\tfor body: Node2D in get_tree().get_nodes_in_group(target_group):\n")
        reports = verify_in_workspace()
        # 去掉接触前置后，第一个物理帧就结算：无接触的目标也掉血（可能掉两次），
        # 同时正向契约的「恰好一次事件」也被多余的节拍打穿。
        free_damage = reports["no_damage_without_contact"]
        free_health = observed(free_damage)
        free_events = observed(free_damage, 1)
        ok("case2: dropping the contact precondition -> damage without contact is caught",
           free_damage.status == behavior.STATUS_MISMATCH
           and isinstance(free_health, int) and free_health < 5
           and isinstance(free_events, int) and free_events >= 1,
           "health=%s events=%s | %s" % (free_health, free_events,
                                        json.dumps(free_damage.to_dict())[:300]))
        extra = reports["damage_on_contact"]
        ok("case2: the surplus tick also breaks the single-event contract",
           extra.status == behavior.STATUS_MISMATCH
           and isinstance(observed(extra), int)
           and (observed(extra) < 4 or (observed(extra, 1) or 0) > 1),
           "health=%s events=%s" % (observed(extra), observed(extra, 1)))
        restore(contactless)
        ok("case2: the contactless script is restored byte-for-byte",
           sha256(script) == baseline["script"])
    finally:
        workspace.close()

    # ---------------- Case 3: 观测缺口 ----------------
    print("=== Case 3: missing evidence never becomes PASS ===")
    absent = probe([overlap("ContactDamage")],
                   [{"check": "health.current", "target": "@actor/Absent", "equals": 4}],
                   behavior_id="absent_target", tag="absent")
    ok("case3: an unresolved observation target -> INSUFFICIENT / check_unavailable",
       absent.get("status") == "INSUFFICIENT"
       and absent.get("reason") == "check_unavailable",
       json.dumps(absent)[:300])
    short = probe([overlap("ContactDamage")],
                  [{"check": "health.current", "target": "@actor/Health", "equals": 4}],
                  window_frames=5, behavior_id="short_window", tag="short_window")
    ok("case3: five frames cannot cover a 0.5s tick -> MISMATCH, never PASS",
       short.get("status") == "MISMATCH" and short.get("reason") == "state_mismatch"
       and short.get("waited_frames") == 5
       and (short.get("checks") or [{}])[0].get("observed") == 5,
       json.dumps({k: short.get(k) for k in ("status", "reason", "waited_frames",
                                             "window_frames", "checks")})[:400])

    # ---------------- Case 4: 重放不一致 ----------------
    print("=== Case 4: inconsistent replays are INSUFFICIENT ===")
    contracts, _ = behavior.build_contracts(FEATURE, FEATURES)
    contract = [item for item in contracts
                if item["behavior"] == "damage_on_contact"][0]

    def drifting_runner(attempt, project_root="", timeout_s=60, godot=""):
        observation = behavior.run_probe(attempt, project_root or PROJECT_ROOT,
                                         godot or _godot, timeout_s)
        payload = observation.get("result")
        if contract and attempt.get("replay_index") == 2 and isinstance(payload, dict):
            payload = json.loads(json.dumps(payload))
            checks = payload.get("checks") or []
            if checks:
                checks[0]["observed"] = (checks[0].get("observed") or 0) + 1
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
       and report.runs[0].get("checks")[0].get("observed") == 4
       and report.runs[1].get("checks")[0].get("observed") == 5,
       json.dumps([run.get("checks") for run in report.runs])[:300])

    # ---------------- Case 5: 契约无效 ----------------
    print("=== Case 5: invalid contracts never reach Godot ===")
    invalid_case("window_zero", {"id": "x", "actions": [overlap("ContactDamage")],
                                 "expected": [{"check": "health.current",
                                               "target": "@actor/Health", "equals": 4}],
                                 "window_frames": 0},
                 "window_frames must be")
    invalid_case("overlap_without_group",
                 {"id": "x",
                  "actions": [{"type": "physics.overlap", "target": "ContactDamage",
                               "params": {"health_max": 5}}],
                  "expected": [{"check": "health.current", "target": "@actor/Health",
                                "equals": 4}], "window_frames": 45},
                 "group")
    invalid_case("scene_escape",
                 {"id": "x", "scene": "../contact_damage/../../escape.tscn",
                  "actions": [overlap("ContactDamage")],
                  "expected": [{"check": "health.current", "target": "@actor/Health",
                                "equals": 4}], "window_frames": 45},
                 "relative path inside")

    # ---------------- Case 6: CLI 与恢复 ----------------
    print("=== Case 6: the CLI fails on a real defect and copies are restored ===")
    copy_root = os.path.join(_tempdir, "cli", "Features")
    shutil.copytree(FEATURES, copy_root)
    cli_script = os.path.join(copy_root, FEATURE, script_name)
    with open(cli_script, "rb") as handle:
        cli_original = handle.read()
    write_text(cli_script, cli_original.decode("utf-8").replace(
        "\thealth.take_damage(damage)\n", "\tpass\n", 1))
    proc = subprocess.run([sys.executable, CLI, "--feature", FEATURE,
                           "--features-dir", copy_root], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=900,
                          stdin=subprocess.DEVNULL, cwd=PROJECT_ROOT)
    ok("case6: the CLI exits non-zero for a muted contact damage",
       proc.returncode == 1 and "MISMATCH" in (proc.stdout or ""),
       "exit=%s out=%s" % (proc.returncode, (proc.stdout or "")[-300:]))
    with open(cli_script, "wb") as handle:
        handle.write(cli_original)
    ok("case6: the CLI fixture copy is restored byte-for-byte",
       sha256(cli_script) == baseline["script"])

    ok("case6: repository Feature files are untouched",
       sha256(os.path.join(FEATURES, FEATURE, script_name)) == baseline["script"]
       and sha256(os.path.join(FEATURES, FEATURE, "ContactDamageFixture.tscn"))
       == baseline["fixture"]
       and sha256(os.path.join(FEATURES, FEATURE, "template.yaml"))
       == baseline["template"])

    # ---------------- Case 7: @actor 信号监听的局部修补 ----------------
    # Phase 1.47 只在探针里补了「动作执行后重试 @actor 监听」。这里证明：拿掉重试，
    # @actor 上的信号断言就只能是 INSUFFICIENT——它绝不会因为“没连上所以 0 次”而假 PASS。
    print("=== Case 7: @actor signal watches stay honest without the retry ===")
    isolated = behavior.BehaviorWorkspace(FEATURES, _godot)
    try:
        probe_copy = os.path.join(isolated.project, ".ai", "tools", "scene_composer",
                                  "probes", "feature_behavior_probe.gd")
        with open(probe_copy, "rb") as handle:
            probe_bytes = handle.read()
        probe_digest = sha256(probe_copy)
        retry_call = ("\t\t# 动作可能刚创建了 @actor（physics.overlap）：现在才可能连接它的信号监听。\n"
                      "\t\t_connect_actor_watches()\n")
        text = probe_bytes.decode("utf-8")
        ok("case7: the probe retry anchor is present", retry_call in text)
        write_text(probe_copy, text.replace(retry_call, "", 1))
        without_retry = behavior.run_probe(contract, isolated.project, _godot, timeout_s=60)
        payload = without_retry.get("result") or {}
        ok("case7: without the retry an @actor signal check is INSUFFICIENT, never PASS",
           payload.get("status") == "INSUFFICIENT"
           and payload.get("reason") == "check_unavailable",
           json.dumps({k: payload.get(k) for k in ("status", "reason", "detail",
                                                   "checks")})[:400])
        with open(probe_copy, "wb") as handle:
            handle.write(probe_bytes)
        ok("case7: the isolated probe copy is restored byte-for-byte",
           sha256(probe_copy) == probe_digest)
    finally:
        isolated.close()


if __name__ == "__main__":
    sys.exit(main())
