#!/usr/bin/env python3
"""Slime Contact E2E Acceptance 测试（Phase 1.48）

正式场景 `Scenes/SlimeContactArena.tscn`（真实 Player + 真实 SlimeEnemy）上的
**接触伤害端到端链**：

    输入 move_right → PlayerController/CharacterBody2D 真实位移
      → 与 SlimeEnemy 的 ContactShape(36×36) 真实重叠
      → ContactDamage 的物理帧节拍结算
      → 玩家自己的 Health.take_damage(1) + health_changed 信号

    Case 1  正向链：3 阶段 PASS、两次重放一致、观测值逐项可追溯
    Case 2  负向：删除 `SlimeEnemy/ContactDamage/ContactShape`（接触通道断开）→ MISMATCH
    Case 3  负向：静音 `contact_damage.gd` 的伤害调用（伤害调用未生效）→ MISMATCH
    Case 4  负向：玩家不在 `players` 组（接触前置条件不满足）→ MISMATCH，且玩家不掉血
    Case 5  负向：观测目标损坏（`Player/Health` 不存在）→ INSUFFICIENT，绝不 PASS
    Case 6  负向：观察窗口短于一个节拍（5 帧）→ MISMATCH（不是 INSUFFICIENT）
    Case 7  负向：不做接触动作却期望伤害 → MISMATCH（链不会凭空成立）
    Case 8  负向：重放不一致 → INSUFFICIENT / replay_inconsistent
    Case 9  非法/越权场景：未登记场景、白名单外路径 → INVALID（不启动 Godot）
    Case 10 CLI 退出码：PASS → 0，MISMATCH → 1
    Case 11 隔离副本逐字节恢复 + 仓库文件哈希不变 + 工作区所有权清理

所有注入都发生在本次运行独占的隔离项目副本里，每步注入后都用 SHA256 验证恢复。
用法:
    python .ai/tools/scene_composer/tests/test_slime_contact_arena.py
"""

import contextlib
import copy
import hashlib
import io
import json
import os
import sys

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
TOOL_DIR = os.path.dirname(_HERE)
TOOLS_DIR = os.path.dirname(TOOL_DIR)
DOTAI = os.path.dirname(TOOLS_DIR)
PROJECT_ROOT = os.path.dirname(DOTAI)

for path in (TOOL_DIR, TOOLS_DIR, _HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import behavior_protocol                                          # noqa: E402
import composite_behavior_protocol as composite_protocol          # noqa: E402
import composite_behavior_evidence as evidence                    # noqa: E402
import runtime_instance_evidence as runtime_evidence              # noqa: E402

_failures = []
CONTRACTS = composite_protocol.CONTRACTS_DIR
SCENE_ID = "slime_contact"
SCENE_REL = os.path.join("Scenes", "SlimeContactArena.tscn")
SLIME_REL = os.path.join("Scenes", "SlimeEnemy.tscn")
PLAYER_REL = os.path.join("Features", "player_movement", "Player.tscn")
CONTACT_SCRIPT = os.path.join("Features", "contact_damage", "contact_damage.gd")
CONTACT_SHAPE_LINE = ('[node name="ContactShape" type="CollisionShape2D" parent="ContactDamage"]\n'
                      'shape = SubResource("RectangleShape2D_ContactShape_1")\n')
PLAYER_GROUP_DECL = 'instance=ExtResource("1_player") groups=["players"]]'

REPO_PROTECTED = [
    SCENE_REL,
    os.path.join("Scenes", "SlimeEnemy.tscn"),
    os.path.join("Features", "player_movement", "Player.tscn"),
    os.path.join("Features", "health", "health.gd"),
    CONTACT_SCRIPT,
    os.path.join(".ai", "context", "composite_behavior_protocol.yaml"),
    os.path.join(".ai", "tools", "scene_composer", "probes",
                 "composite_behavior_manifest.json"),
    os.path.join(".ai", "context", "composite_scenes", "slime_contact.yaml"),
]

STAGE_APPROACH = "approach_without_contact_deals_no_damage"
STAGE_CONTACT = "contact_deals_one_tick_of_damage"
STAGE_LEAVE = "leaving_contact_stops_damage"


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def write_bytes(path: str, data: bytes) -> None:
    with open(path, "wb") as handle:
        handle.write(data)


def read_text(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


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


def snapshot(paths) -> dict:
    return {path: sha256(os.path.join(PROJECT_ROOT, path)) for path in paths}


def stages_by_id(report) -> dict:
    return {run["id"]: run for run in (report.runs[0].get("stages") or [])}


def checks_for(report, stage_id: str, target: str = "") -> list:
    return [check for check in report.checks
            if check.get("stage") == stage_id
            and (not target or check.get("target") == target)]


def check_for(report, stage_id: str, target: str, check_name: str = "") -> dict:
    for check in checks_for(report, stage_id, target):
        if not check_name or check.get("check") == check_name:
            return check
    return {}


def run_cli(argv) -> tuple:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = evidence.main(argv)
    return code, buffer.getvalue()


def mutated(raw, mutate) -> tuple:
    """深拷贝契约 -> 变异 -> 通过 Python 校验（得到可执行契约或错误列表）。"""
    data = copy.deepcopy(raw)
    mutate(data)
    protocol = composite_protocol.load_protocol()
    behavior = behavior_protocol.load_protocol()
    return protocol.validate_contract(data, SCENE_ID, behavior)


def main() -> int:
    print("=== Slime Contact E2E Acceptance (Phase 1.48) ===")
    godot = runtime_evidence.find_godot(PROJECT_ROOT)
    if not godot:
        print("SKIP: godot executable not found; the contact chain cannot be observed")
        return 1

    repo_hashes = snapshot(REPO_PROTECTED)
    behavior = behavior_protocol.load_protocol()
    protocol = composite_protocol.load_protocol()
    raw, read_error = composite_protocol.load_contract_file(
        os.path.join(CONTRACTS, SCENE_ID + ".yaml"))
    ok("setup: the slime_contact contract file is readable", read_error == "", read_error)

    # ---------------- Case 1: 协议 / manifest / 契约形状 ----------------
    print("=== Case 1: protocol, manifest and contract shape ===")
    ok("case1: slime_contact is whitelisted to the formal arena scene",
       protocol.allowed_scene(SCENE_ID) == "Scenes/SlimeContactArena.tscn",
       protocol.allowed_scene(SCENE_ID))
    ok("case1: the manifest has no drift",
       composite_protocol.check_manifest(protocol) == [],
       str(composite_protocol.check_manifest(protocol)))
    ok("case1: regenerating the manifest is byte-identical",
       read_text(composite_protocol.MANIFEST_PATH) == protocol.manifest_text())
    contracts, invalid = composite_protocol.build_contracts(CONTRACTS, protocol, behavior)
    ok("case1: every declared contract is valid", invalid == [], str(invalid))
    by_id = {contract["scene_id"]: contract for contract in contracts}
    chain = by_id.get(SCENE_ID) or {}
    ok("case1: the chain declares three ordered stages",
       [stage["id"] for stage in chain.get("stages", [])] ==
       [STAGE_APPROACH, STAGE_CONTACT, STAGE_LEAVE],
       str([stage["id"] for stage in chain.get("stages", [])]))
    ok("case1: the chain declares the real components it exercises",
       chain.get("features") == ["player_movement", "chase_movement",
                                 "contact_damage", "health"],
       str(chain.get("features")))
    ok("case1: no stage uses a fixture action (no state.set_property anywhere)",
       all(action["type"] != "state.set_property"
           for stage in chain.get("stages", []) for action in stage["actions"]),
       str([[action["type"] for action in stage["actions"]]
            for stage in chain.get("stages", [])]))
    stage_frames = {stage["id"]: stage["frames"] for stage in chain.get("stages", [])}
    ok("case1: every stage advances real physics frames before asserting",
       all(frames > 0 for frames in stage_frames.values()), str(stage_frames))

    workspace = evidence.CompositeWorkspace(evidence._new_run_id("slime"), godot, 180,
                                            PROJECT_ROOT)
    project = workspace.project
    try:
        # ---------------- Case 1b: 正向端到端链 ----------------
        print("=== Case 1b: the real contact chain PASSes and replays identically ===")
        report = evidence.verify_contract(chain, project, godot, replay=2, timeout_s=120,
                                         run_id=evidence._new_run_id("slime_ok"))
        ok("case1: the chain PASSes", report.status == evidence.STATUS_PASS,
           "%s | %s" % (report.status, report.detail))
        ok("case1: every stage completed in order",
           report.completed_stages == report.stage_ids and report.failed_stage is None,
           str(report.completed_stages))
        ok("case1: two replays agree on the semantic result", report.replay_consistent,
           str(report.replay_count))
        ok("case1: the probe really executed actions", report.runs[0]["action_executed"])
        ok("case1: evidence artifacts were written",
           all(os.path.isfile(path) for artifacts in report.evidence.values()
               for path in artifacts.values() if path.endswith(".json")),
           str(list(report.evidence)))

        position_1 = check_for(report, STAGE_APPROACH, "Player", "node2d.position")
        ok("case1: stage 1 moved the player towards the slime without touching it",
           isinstance(position_1.get("observed"), float)
           and -130.0 <= position_1["observed"] <= -60.0,
           str(position_1))
        ok("case1: stage 1 saw full health and no damage event",
           check_for(report, STAGE_APPROACH, "Player/Health",
                     "health.current").get("observed") == 10
           and check_for(report, STAGE_APPROACH, "Player/Health",
                         "signal").get("observed") == 0,
           json.dumps(checks_for(report, STAGE_APPROACH))[:300])

        contact_position = check_for(report, STAGE_CONTACT, "Player", "node2d.position")
        ok("case1: stage 2 stopped exactly at the slime body (real contact band)",
           isinstance(contact_position.get("observed"), float)
           and -34.0 <= contact_position["observed"] <= -26.0,
           str(contact_position))
        ok("case1: the contact cost exactly one point of health",
           check_for(report, STAGE_CONTACT, "Player/Health",
                     "health.current").get("observed") == 9,
           str(check_for(report, STAGE_CONTACT, "Player/Health", "health.current")))
        ok("case1: exactly one damage event was emitted",
           check_for(report, STAGE_CONTACT, "Player/Health",
                     "signal").get("observed") == 1,
           str(check_for(report, STAGE_CONTACT, "Player/Health", "signal")))
        ok("case1: damage is one-directional (the slime keeps 5 health)",
           check_for(report, STAGE_CONTACT, "SlimeEnemy/Health",
                     "health.current").get("observed") == 5)
        ok("case1: the slime did not move (no chase target configured)",
           check_for(report, STAGE_CONTACT, "SlimeEnemy",
                     "node2d.position").get("observed") == 0.0,
           str(checks_for(report, STAGE_CONTACT, "SlimeEnemy")))

        ok("case1: stage 3 walked away from the contact band",
           isinstance(check_for(report, STAGE_LEAVE, "Player",
                               "node2d.position").get("observed"), float)
           and -140.0 <= check_for(report, STAGE_LEAVE, "Player",
                                   "node2d.position")["observed"] <= -80.0,
           str(check_for(report, STAGE_LEAVE, "Player", "node2d.position")))
        ok("case1: leaving contact stopped the damage (still 9 after 1.5 ticks)",
           check_for(report, STAGE_LEAVE, "Player/Health",
                     "health.current").get("observed") == 9
           and check_for(report, STAGE_LEAVE, "Player/Health",
                         "signal").get("observed") == 1,
           json.dumps(checks_for(report, STAGE_LEAVE))[:300])
        health_readings = [check.get("observed") for check in report.checks
                           if check.get("check") == "health.current"
                           and check.get("target") == "Player/Health"]
        ok("case1: health readings are monotone and match the event counts",
           health_readings == [10, 9, 9], str(health_readings))

        # ---------------- Case 2: 接触通道断开 ----------------
        print("=== Case 2: removing the contact shape makes the contact damage vanish ===")
        scene_path = os.path.join(project, SCENE_REL)
        scene_bytes = read_bytes(scene_path)
        slime_path = os.path.join(project, SLIME_REL)
        slime_bytes = read_bytes(slime_path)
        ok("case2: the enemy scene contains the contact shape node",
           CONTACT_SHAPE_LINE.encode() in slime_bytes)
        write_bytes(slime_path, slime_bytes.replace(CONTACT_SHAPE_LINE.encode(), b""))
        no_shape = evidence.verify_contract(chain, project, godot, replay=1, timeout_s=120,
                                            run_id=evidence._new_run_id("no_shape"))
        write_bytes(slime_path, slime_bytes)
        ok("case2: the isolated enemy scene is restored byte-for-byte",
           sha256(slime_path) == hashlib.sha256(slime_bytes).hexdigest())
        ok("case2: the chain no longer PASSes", no_shape.status != evidence.STATUS_PASS,
           no_shape.status)
        ok("case2: it fails exactly at the contact stage",
           no_shape.failed_stage == STAGE_CONTACT and no_shape.reason == "state_mismatch",
           "%s / %s" % (no_shape.failed_stage, no_shape.reason))
        ok("case2: the player still reached the slime, so the failure is the damage",
           isinstance(check_for(no_shape, STAGE_CONTACT, "Player",
                                "node2d.position").get("observed"), float)
           and -34.0 <= check_for(no_shape, STAGE_CONTACT, "Player",
                                  "node2d.position")["observed"] <= -26.0,
           str(check_for(no_shape, STAGE_CONTACT, "Player", "node2d.position")))
        ok("case2: health stayed at 10 and no event was emitted",
           check_for(no_shape, STAGE_CONTACT, "Player/Health",
                     "health.current").get("observed") == 10
           and check_for(no_shape, STAGE_CONTACT, "Player/Health",
                         "signal").get("observed") == 0,
           json.dumps(checks_for(no_shape, STAGE_CONTACT))[:300])
        ok("case2: the leaving stage never ran",
           no_shape.completed_stages == [STAGE_APPROACH],
           str(no_shape.completed_stages))

        # ---------------- Case 3: 伤害调用未生效 ----------------
        print("=== Case 3: a muted damage call fails the chain (not the observation) ===")
        script_path = os.path.join(project, CONTACT_SCRIPT)
        script_bytes = read_bytes(script_path)
        script_text = script_bytes.decode("utf-8")
        ok("case3: the component delegates damage to Health.take_damage",
           "health.take_damage(damage)" in script_text)
        write_bytes(script_path, script_text.replace(
            "health.take_damage(damage)", "pass").encode("utf-8"))
        muted = evidence.verify_contract(chain, project, godot, replay=1, timeout_s=120,
                                        run_id=evidence._new_run_id("muted"))
        write_bytes(script_path, script_bytes)
        ok("case3: the isolated script is restored byte-for-byte",
           sha256(script_path) == hashlib.sha256(script_bytes).hexdigest())
        ok("case3: the chain reports MISMATCH at the contact stage",
           muted.status == evidence.STATUS_MISMATCH
           and muted.failed_stage == STAGE_CONTACT,
           "%s / %s" % (muted.status, muted.failed_stage))
        ok("case3: the reason is the wrong game state, not an unavailable check",
           muted.reason == "state_mismatch", muted.reason)
        ok("case3: the mismatch names the player health check",
           "health.current" in str(muted.detail), muted.detail[:200])

        # ---------------- Case 4: 接触前置条件不满足 ----------------
        print("=== Case 4: a player outside the target group is never damaged ===")
        scene_bytes = read_bytes(scene_path)
        ok("case4: the player instance declares the players group",
           PLAYER_GROUP_DECL.encode() in scene_bytes)
        write_bytes(scene_path, scene_bytes.replace(
            PLAYER_GROUP_DECL.encode(),
            'instance=ExtResource("1_player")]'.encode()))
        no_group = evidence.verify_contract(chain, project, godot, replay=1, timeout_s=120,
                                           run_id=evidence._new_run_id("no_group"))
        write_bytes(scene_path, scene_bytes)
        ok("case4: the isolated scene is restored byte-for-byte",
           sha256(scene_path) == hashlib.sha256(scene_bytes).hexdigest())
        ok("case4: the chain is MISMATCH at the contact stage",
           no_group.status == evidence.STATUS_MISMATCH
           and no_group.failed_stage == STAGE_CONTACT,
           "%s / %s" % (no_group.status, no_group.failed_stage))
        ok("case4: the player overlapped the slime but kept full health",
           isinstance(check_for(no_group, STAGE_CONTACT, "Player",
                                "node2d.position").get("observed"), float)
           and -34.0 <= check_for(no_group, STAGE_CONTACT, "Player",
                                  "node2d.position")["observed"] <= -26.0
           and check_for(no_group, STAGE_CONTACT, "Player/Health",
                         "health.current").get("observed") == 10,
           json.dumps(checks_for(no_group, STAGE_CONTACT))[:300])

        # ---------------- Case 5: 观测目标损坏 ----------------
        print("=== Case 5: a broken observation target is INSUFFICIENT, never PASS ===")
        player_path = os.path.join(project, PLAYER_REL)
        player_bytes = read_bytes(player_path)
        ok("case5: the player scene provides the Health child the chain observes",
           b'[node name="Health" parent="."' in player_bytes)
        write_bytes(player_path, player_bytes.replace(
            b'[node name="Health" parent="."', b'[node name="HealthGone" parent="."'))
        missing = evidence.verify_contract(chain, project, godot, replay=1, timeout_s=120,
                                          run_id=evidence._new_run_id("no_health"))
        write_bytes(player_path, player_bytes)
        ok("case5: the isolated player scene is restored byte-for-byte",
           sha256(player_path) == hashlib.sha256(player_bytes).hexdigest())
        ok("case5: the chain never reports PASS",
           missing.status != evidence.STATUS_PASS, missing.status)
        ok("case5: it is INSUFFICIENT (the evidence could not be collected)",
           missing.status == evidence.STATUS_INSUFFICIENT, missing.status)
        ok("case5: the missing health observation is named as the unmet precondition",
           missing.reason == "precondition_unmet"
           and "health.current" in missing.detail,
           "%s / %s" % (missing.reason, missing.detail))
        ok("case5: no stage ran and no action was executed",
           missing.completed_stages == [] and not missing.runs[0]["action_executed"],
           str(missing.completed_stages))

        missing_target, errors = mutated(raw, lambda data: data["stages"][1][
            "expected"].__setitem__(1, {"check": "health.current",
                                        "target": "Player/MissingHealth",
                                        "equals": 9}))
        ok("case5: the missing-target contract is still valid", errors == [],
           "; ".join(errors))
        unavailable = evidence.verify_contract(missing_target, project, godot, replay=1,
                                               timeout_s=120,
                                               run_id=evidence._new_run_id("no_target"))
        ok("case5: an unavailable stage target is INSUFFICIENT / check_unavailable",
           unavailable.status == evidence.STATUS_INSUFFICIENT
           and unavailable.reason == "check_unavailable",
           "%s / %s" % (unavailable.status, unavailable.reason))
        ok("case5: the earlier stage is still recorded as completed",
           unavailable.completed_stages == [STAGE_APPROACH],
           str(unavailable.completed_stages))

        # ---------------- Case 6: 观察窗口不足 ----------------
        print("=== Case 6: a window shorter than one tick is MISMATCH, not INSUFFICIENT ===")
        short, errors = mutated(raw, lambda data: data["stages"][1].update(window_frames=5))
        ok("case6: the shortened-window contract is still valid", errors == [],
           "; ".join(errors))
        short_report = evidence.verify_contract(short, project, godot, replay=1,
                                                timeout_s=120,
                                                run_id=evidence._new_run_id("short"))
        ok("case6: the result is MISMATCH", short_report.status == evidence.STATUS_MISMATCH,
           short_report.status)
        ok("case6: the tick had no chance to fire inside 5 frames",
           check_for(short_report, STAGE_CONTACT, "Player/Health",
                     "health.current").get("observed") == 10,
           str(check_for(short_report, STAGE_CONTACT, "Player/Health", "health.current")))
        ok("case6: the failing stage is the contact stage",
           short_report.failed_stage == STAGE_CONTACT, str(short_report.failed_stage))

        # ---------------- Case 7: 无接触却期望伤害 ----------------
        print("=== Case 7: expecting damage without any contact is refused ===")
        no_move, errors = mutated(raw, lambda data: data["stages"][1].update(
            actions=[{"type": "simulation.advance_frames", "params": {"frames": 45}}]))
        ok("case7: the no-movement contract is still valid", errors == [],
           "; ".join(errors))
        no_move_report = evidence.verify_contract(no_move, project, godot, replay=1,
                                                  timeout_s=120,
                                                  run_id=evidence._new_run_id("no_move"))
        ok("case7: it reports MISMATCH at the contact stage",
           no_move_report.status == evidence.STATUS_MISMATCH
           and no_move_report.failed_stage == STAGE_CONTACT,
           "%s / %s" % (no_move_report.status, no_move_report.failed_stage))
        idle_x = check_for(no_move_report, STAGE_CONTACT, "Player",
                           "node2d.position").get("observed")
        ok("case7: the player stayed where stage 1 left it and was never damaged",
           isinstance(idle_x, float) and -100.0 <= idle_x <= -80.0
           and check_for(no_move_report, STAGE_CONTACT, "Player/Health",
                         "health.current").get("observed") == 10,
           json.dumps(checks_for(no_move_report, STAGE_CONTACT))[:300])

        # ---------------- Case 8: 重放不一致 ----------------
        print("=== Case 8: inconsistent replays never stay PASS ===")

        def payload_for(status: str, stage_status: str = "PASS") -> dict:
            stages = []
            for stage_id in (STAGE_APPROACH, STAGE_CONTACT, STAGE_LEAVE):
                item_status = stage_status if stage_id == STAGE_CONTACT else "PASS"
                stages.append({
                    "id": stage_id, "status": item_status, "reason": "",
                    "checks": [{"check": "health.current", "target": "Player/Health",
                                "entry": "", "expected": 10, "observed": 10,
                                "status": "PASS" if item_status == "PASS"
                                else "STATE_MISMATCH",
                                "first_observed_frame": 0}],
                })
            return {"status": status,
                    "reason": "ok" if status == "PASS" else "state_mismatch",
                    "detail": "", "action_executed": True,
                    "completed_stages": [] if status != "PASS" else
                    [STAGE_APPROACH, STAGE_CONTACT, STAGE_LEAVE],
                    "failed_stage": None if status == "PASS" else STAGE_CONTACT,
                    "stages": stages,
                    "checks": [check for stage in stages for check in stage["checks"]]}

        calls = {"n": 0}

        def alternating_runner(attempt, project_root="", timeout_s=0, godot=""):
            calls["n"] += 1
            if calls["n"] == 1:
                payload = payload_for("PASS")
            else:
                payload = payload_for("MISMATCH", "STATE_MISMATCH")
            return {"result": payload, "stdout": "", "stderr": "", "exit_code": 0,
                    "duration": 0.0, "timed_out": False, "artifacts": {}}

        inconsistent = evidence.verify_contract(chain, project, godot, replay=2,
                                                timeout_s=60, runner=alternating_runner,
                                                run_id="slime-replay-test")
        ok("case8: a PASS that is not reproducible is downgraded",
           inconsistent.status == evidence.STATUS_INSUFFICIENT
           and inconsistent.reason == "replay_inconsistent",
           "%s / %s" % (inconsistent.status, inconsistent.reason))
        ok("case8: the inconsistency is reported, not hidden",
           not inconsistent.replay_consistent
           and len(inconsistent.runs) == 2)

        # ---------------- Case 9: 非法 / 越权场景 ----------------
        print("=== Case 9: unlisted scenes and paths are INVALID before Godot starts ===")

        def expect_invalid(name: str, mutate, needle: str) -> None:
            contract, errors = mutated(raw, mutate)
            ok("case9: %s is INVALID" % name,
               contract is None and any(needle in message for message in errors),
               "; ".join(errors)[:300])

        expect_invalid("an unlisted scene file",
                       lambda data: data.update(scene="Scenes/SlimeEnemy.tscn"),
                       "must be exactly")
        expect_invalid("an arbitrary scene path",
                       lambda data: data.update(scene="../Scenes/EscapeRoom.tscn"),
                       "must be exactly")
        expect_invalid("an undeclared scene id",
                       lambda data: data.update(scene_id="slime_arena"),
                       "does not match the file name")
        expect_invalid("a fixture state write",
                       lambda data: data["stages"][1]["actions"].append(
                           {"type": "state.set_property", "target": "Player/Health",
                            "params": {"property": "trigger_switch.trigger_mode",
                                       "value": "Toggle"}}),
                       "denies")

        probe_contract = {
            "scene_id": SCENE_ID,
            "scene": "res://Scenes/../project.godot",
            "run_id": "slime-path-escape",
            "replay_index": 1,
            "preconditions": [],
            "stages": [
                {"id": "one",
                 "actions": [{"type": "simulation.advance_frames", "target": ".",
                              "params": {"frames": 5}}],
                 "expected": [{"check": "health.current", "target": "Player/Health",
                               "equals": 10}],
                 "window_frames": 5},
                {"id": "two",
                 "actions": [{"type": "simulation.advance_frames", "target": ".",
                              "params": {"frames": 5}}],
                 "expected": [{"check": "health.current", "target": "Player/Health",
                               "equals": 10}],
                 "window_frames": 5},
            ],
        }
        payload = evidence.run_probe(probe_contract, project, godot,
                                     timeout_s=60).get("result") or {}
        ok("case9: the probe rejects a path outside the allowlist",
           payload.get("status") == "INVALID"
           and "allowlist" in str(payload.get("detail", "")),
           json.dumps(payload)[:300])

        # ---------------- Case 10: CLI 退出码 ----------------
        print("=== Case 10: CLI exit codes for the contact chain ===")
        code, output = run_cli(["--scene", SCENE_ID, "--replay", "1"])
        ok("case10: a passing chain exits 0", code == 0, output[-300:])
        ok("case10: the CLI reports three passing stages",
           "3/3" in output and "PASS" in output, output[-300:])
        ok("case10: the CLI cleaned up its own workspace",
           "workspace removed=True" in output, output[-300:])

        bad_dir = os.path.join(DOTAI, "tmp", "slime_bad_contracts")
        os.makedirs(bad_dir, exist_ok=True)
        bad_raw = copy.deepcopy(raw)
        bad_raw["stages"][1]["expected"][1]["equals"] = 8
        write_text(os.path.join(bad_dir, SCENE_ID + ".yaml"),
                   yaml.safe_dump(bad_raw, sort_keys=False, allow_unicode=True))
        code, output = run_cli(["--scene", SCENE_ID, "--replay", "1",
                                "--contracts-dir", bad_dir])
        ok("case10: a MISMATCH exits 1", code == 1, output[-300:])
        ok("case10: the failing contact stage is named",
           STAGE_CONTACT in output, output[-400:])

        # ---------------- Case 11: 副本恢复 / 仓库保护 ----------------
        print("=== Case 11: isolated copies are restored and the repo is untouched ===")
        ok("case11: the isolated arena scene matches the repository scene again",
           sha256(scene_path) == repo_hashes[SCENE_REL],
           "%s vs %s" % (sha256(scene_path), repo_hashes[SCENE_REL]))
        ok("case11: the isolated enemy scene is unmodified",
           sha256(slime_path) == repo_hashes[SLIME_REL])
        ok("case11: the isolated contact script is unmodified",
           sha256(script_path) == repo_hashes[CONTACT_SCRIPT])
        ok("case11: the whole chain still PASSes after all injections",
           evidence.verify_contract(chain, project, godot, replay=1, timeout_s=120,
                                    run_id=evidence._new_run_id("restored")).status
           == evidence.STATUS_PASS)
    finally:
        if os.path.isdir(workspace.root):
            cleanup = workspace.close()
            ok("teardown: the test workspace is removed", cleanup["removed"] is True,
               json.dumps(cleanup))

    ok("case11: no repository file changed during the run", snapshot(REPO_PROTECTED) ==
       repo_hashes,
       str({path: (repo_hashes[path], sha256(os.path.join(PROJECT_ROOT, path)))
            for path in REPO_PROTECTED
            if repo_hashes[path] != sha256(os.path.join(PROJECT_ROOT, path))}))
    ok("case11: the repo manifest still matches the protocol",
       composite_protocol.check_manifest(composite_protocol.load_protocol()) == [])
    ok("case11: the behaviour manifest still matches its protocol",
       behavior_protocol.check_manifest(behavior_protocol.load_protocol()) == [])

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all slime contact acceptance checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
