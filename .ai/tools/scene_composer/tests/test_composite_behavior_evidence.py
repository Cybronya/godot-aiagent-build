#!/usr/bin/env python3
"""Composite Scene Behavior Evidence 测试（Phase 1.46）

真实组合场景（EscapeRoom / SurvivalArena）+ 分阶段受限动作 → 中间与最终状态 /
事件次数与参数 → 重放一致性 / 负向对照 / 资源所有权。

    Case 1  组合协议 / manifest / 探针能力门禁（含非法协议与漂移）
    Case 2  EscapeRoom 端到端链：4 阶段全 PASS、两次重放一致、观测值可追溯
    Case 3  SurvivalArena（1 开关 → 2 门）：2 阶段 PASS、两次重放一致
    Case 4  非法契约：未知场景 / 场景路径不符 / 禁止动作 / 单阶段 / 零帧纯否定 /
            未知观测 / 路径越界 / 窗口越界 / 预算超限 / 重复阶段 / 文件名不符
    Case 5  负向对照：断开 SwitchB→ConditionGate 连接 → 第 3 阶段 MISMATCH
    Case 6  负向对照：门报告已开但仍阻挡 → 第 4 阶段 MISMATCH（不是靠 is_open 通过）
    Case 7  观测不可用（目标节点缺失）→ INSUFFICIENT / check_unavailable
    Case 8  前置条件不满足 → INSUFFICIENT / precondition_unmet，动作未执行
    Case 9  中间状态预期错误 → MISMATCH，且后续阶段未执行（部分链绝不 PASS）
    Case 10 探针层零帧门禁：绕过 Python 校验也拒绝，不判 PASS
    Case 11 重放不一致 → INSUFFICIENT / replay_inconsistent（绝不保留 PASS）
    Case 12 CLI：PASS=0 / MISMATCH=1 / INVALID=1 / INSUFFICIENT(--require-composite)=1
    Case 13 资源所有权：只删除自己的副本；他人/未知副本只报告不删除；异常路径清理
    Case 14 仓库黄金文件与契约哈希不变

所有缺陷注入均在本次运行独占的隔离项目副本内完成，并逐字节恢复 + 哈希比对。

用法:
    python .ai/tools/scene_composer/tests/test_composite_behavior_evidence.py
"""

import contextlib
import copy
import hashlib
import io
import json
import os
import shutil
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
SCENE_ROOT = os.path.join(PROJECT_ROOT, "Scenes")
CONTRACTS = composite_protocol.CONTRACTS_DIR

ESCAPE_SCENE = os.path.join("Scenes", "EscapeRoom.tscn")
DOOR_SCRIPT = os.path.join("Features", "openable_door", "openable_door.gd")
SWITCH_LINK = (
    "[connection signal=\"activated\" from=\"Mechanism/SwitchB\" "
    "to=\"Mechanism/ConditionGate\" method=\"set_condition\" binds=[\"switch_b\"]]\n")
DOOR_COLLISION_BLOCK = ("\tif _collision != null:\n"
                        "\t\t_collision.set_deferred(\"disabled\", value)\n")

REPO_PROTECTED = [
    os.path.join("Scenes", "EscapeRoom.tscn"),
    os.path.join("Scenes", "escape_room.gd"),
    os.path.join("Scenes", "SurvivalArena.tscn"),
    DOOR_SCRIPT,
    os.path.join("Features", "trigger_switch", "trigger_switch.gd"),
    os.path.join("Features", "condition_gate", "condition_gate.gd"),
    os.path.join("Features", "player_movement", "player_controller.gd"),
    os.path.join(".ai", "context", "composite_behavior_protocol.yaml"),
    os.path.join(".ai", "context", "composite_scenes", "escape_room.yaml"),
    os.path.join(".ai", "context", "composite_scenes", "survival_arena.yaml"),
]


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


def check_for(report, stage_id: str, target: str) -> dict:
    for check in report.checks:
        if check.get("stage") == stage_id and check.get("target") == target:
            return check
    return {}


def run_cli(argv) -> tuple:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = evidence.main(argv)
    return code, buffer.getvalue()


def cli_json(output: str) -> dict:
    start = output.find("{")
    if start < 0:
        return {}
    try:
        return json.loads(output[start:])
    except ValueError:
        return {}


def contract_from(raw, mutate) -> tuple:
    """深拷贝原始契约 -> 施加变异 -> 通过 Python 校验得到可执行契约。"""
    data = copy.deepcopy(raw)
    mutate(data)
    protocol = composite_protocol.load_protocol()
    behavior = behavior_protocol.load_protocol()
    return protocol.validate_contract(data, "escape_room", behavior)


def main() -> int:
    print("=== Composite Scene Behavior Evidence (Phase 1.46) ===")
    godot = runtime_evidence.find_godot(PROJECT_ROOT)
    if not godot:
        print("SKIP: godot executable not found; composite evidence cannot be verified")
        return 1

    repo_hashes = snapshot(REPO_PROTECTED)
    behavior = behavior_protocol.load_protocol()
    protocol = composite_protocol.load_protocol()
    base_raw, read_error = composite_protocol.load_contract_file(
        os.path.join(CONTRACTS, "escape_room.yaml"))
    ok("setup: the EscapeRoom contract file is readable", read_error == "", read_error)

    workspace = evidence.CompositeWorkspace(evidence._new_run_id("test"), godot, 120,
                                            PROJECT_ROOT)
    project = workspace.project
    foreign = None
    try:
        # ---------------- Case 1: 协议 / manifest / 探针能力 ----------------
        print("=== Case 1: composite protocol, manifest and probe capabilities ===")
        ok("case1: the composite protocol extends behavior protocol v2",
           protocol.version == composite_protocol.SUPPORTED_PROTOCOL_VERSION == 1
           and protocol.extends_version == behavior.version == 2,
           "%s/%s/%s" % (protocol.version, protocol.extends_version, behavior.version))
        ok("case1: manifest has no drift", composite_protocol.check_manifest(protocol) == [],
           str(composite_protocol.check_manifest(protocol)))
        ok("case1: regenerating the manifest is byte-identical",
           read_text(composite_protocol.MANIFEST_PATH) == protocol.manifest_text())
        ok("case1: the scene allowlist only contains real project scenes",
           sorted(protocol.scenes) == ["escape_room", "slime_contact", "survival_arena"]
           and all(os.path.isfile(os.path.join(PROJECT_ROOT, *path.split("/")))
                   for path in protocol.scenes.values()),
           str(protocol.scenes))
        ok("case1: the composite protocol denies fixture property writes",
           [item["action"] for item in protocol.denied_actions] == ["state.set_property"],
           str(protocol.denied_actions))

        capabilities = composite_protocol.probe_capabilities(project, godot)
        ok("case1: probe capabilities match the protocols",
           composite_protocol.check_capabilities(protocol, behavior, capabilities) == [],
           str(composite_protocol.check_capabilities(protocol, behavior, capabilities)))
        ok("case1: the composite probe does not implement the denied action",
           "state_set_property" not in (capabilities.get("actions") or []),
           str(capabilities.get("actions")))
        ok("case1: the composite probe implements the gate observation",
           "observe_gate_is_fulfilled" in (capabilities.get("observations") or []))

        temp = os.path.join(DOTAI, "tmp", "composite_protocol_cases")
        os.makedirs(temp, exist_ok=True)

        def expect_protocol_error(name: str, text: str, needle: str) -> None:
            path = os.path.join(temp, name + ".yaml")
            write_text(path, text)
            try:
                composite_protocol.load_protocol(path)
                ok("case1: %s is rejected" % name, False, "no error")
            except composite_protocol.CompositeProtocolError as exc:
                ok("case1: %s is rejected" % name, needle in str(exc), str(exc))

        source = read_text(composite_protocol.PROTOCOL_PATH)
        expect_protocol_error("bad_version", source.replace(
            "protocol_version: 1", "protocol_version: 2"), "incompatible")
        expect_protocol_error("bad_extends", source.replace(
            "  version: 2", "  version: 1"), "does not match behavior protocol")
        expect_protocol_error("unknown_scene", source.replace(
            "  escape_room: Scenes/EscapeRoom.tscn",
            "  escape_room: Scenes/EscapeRoom.tscn\n  ghost_room: Scenes/Ghost.tscn"),
            "not an existing .tscn")
        expect_protocol_error("path_escape", source.replace(
            "  escape_room: Scenes/EscapeRoom.tscn",
            "  escape_room: Scenes/../project.godot"), "not an existing .tscn")
        expect_protocol_error("bad_limit", source.replace(
            "  max_window_frames: 120", "  max_window_frames: 0"), "positive integer")
        expect_protocol_error("limit_order", source.replace(
            "  max_total_frames: 1200", "  max_total_frames: 60"),
            "must not exceed max_total_frames")
        expect_protocol_error("unknown_denied_action", source.replace(
            "  - action: state.set_property", "  - action: state.teleport"),
            "unknown action")
        expect_protocol_error("duplicate_key", source.replace(
            "protocol_version: 1\n", "protocol_version: 1\nprotocol_version: 1\n"),
            "duplicate key")

        drifted = os.path.join(temp, "drifted_manifest.json")
        payload = protocol.manifest()
        payload["limits"]["max_total_frames"] = 1
        write_text(drifted, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        ok("case1: a drifted manifest is detected",
           composite_protocol.check_manifest(protocol, drifted) != [],
           str(composite_protocol.check_manifest(protocol, drifted)))

        # ---------------- Case 2: EscapeRoom 端到端链 ----------------
        print("=== Case 2: the EscapeRoom chain is verified end to end ===")
        contracts, invalid = composite_protocol.build_contracts(CONTRACTS, protocol, behavior)
        ok("case2: both declared contracts are valid", invalid == [], str(invalid))
        by_id = {contract["scene_id"]: contract for contract in contracts}
        escape = by_id.get("escape_room") or {}
        contract = escape
        ok("case2: the EscapeRoom contract declares four ordered stages",
           [stage["id"] for stage in escape.get("stages", [])] == [
               "closed_door_blocks_traversal",
               "switch_a_partial_condition_keeps_door_closed",
               "switch_b_fulfils_gate_and_opens_door",
               "player_traverses_opened_gap"],
           str([stage["id"] for stage in escape.get("stages", [])]))

        report = evidence.verify_contract(escape, project, godot, replay=2, timeout_s=120,
                                         run_id=evidence._new_run_id("escape"))
        ok("case2: the chain PASSes", report.status == evidence.STATUS_PASS,
           "%s | %s" % (report.status, report.detail))
        ok("case2: every stage completed in order",
           report.completed_stages == report.stage_ids and report.failed_stage is None,
           str(report.completed_stages))
        ok("case2: two replays agree on the semantic result", report.replay_consistent,
           str(report.replay_count))

        steps = stages_by_id(report)
        ok("case2: no stage was decided without an observation window",
           all(int(step.get("window_frames") or 0) >= 1 for step in steps.values())
           and all(bool(step.get("checks")) for step in steps.values()),
           str({key: len(value.get("checks") or []) for key, value in steps.items()}))

        blocked = check_for(report, "closed_door_blocks_traversal", "Player")
        ok("case2: the closed door physically blocked the player",
           isinstance(blocked.get("observed"), float) and 320.0 <= blocked["observed"] <= 340.0,
           str(blocked))
        closed_events = [check.get("observed") for check in report.checks
                         if check.get("stage") == "closed_door_blocks_traversal"
                         and check.get("check") == "signal"]
        ok("case2: the door was closed and had emitted no state event",
           check_for(report, "closed_door_blocks_traversal",
                     "Mechanism/ExitDoor").get("observed") is False
           and closed_events == [0], str(closed_events))

        ok("case2: with only switch A the gate stayed unfulfilled",
           check_for(report, "switch_a_partial_condition_keeps_door_closed",
                     "Mechanism/ConditionGate").get("observed") is False)
        ok("case2: the partial state produced no gate/door event",
           [check.get("observed") for check in report.checks
            if check.get("stage") == "switch_a_partial_condition_keeps_door_closed"
            and check.get("check") == "signal"] == [0, 0])

        opened = [check for check in report.checks
                  if check.get("stage") == "switch_b_fulfils_gate_and_opens_door"
                  and check.get("check") == "signal"]
        ok("case2: the second switch flipped the gate exactly once with arg true",
           len(opened) == 2 and all(check.get("observed") == 1 for check in opened)
           and opened[0].get("expected") == 1,
           json.dumps(opened)[:300])
        ok("case2: the gate and the door ended open",
           check_for(report, "switch_b_fulfils_gate_and_opens_door",
                     "Mechanism/ConditionGate").get("observed") is True
           and check_for(report, "switch_b_fulfils_gate_and_opens_door",
                         "Mechanism/ExitDoor").get("observed") is True)

        traversed = check_for(report, "player_traverses_opened_gap", "Player")
        ok("case2: the player physically crossed the former doorway",
           isinstance(traversed.get("observed"), float) and traversed["observed"] > 384.0,
           str(traversed))
        ok("case2: the traversal used the same player and the same y lane",
           check_for(report, "player_traverses_opened_gap", "Player").get("observed", 0)
           > blocked.get("observed", 0))
        ok("case2: evidence artifacts are kept for the run",
           all(os.path.isfile(path) for artifacts in report.evidence.values()
               for path in artifacts.values() if path.endswith(".json")),
           str(list(report.evidence)))

        # ---------------- Case 3: SurvivalArena 对照 ----------------
        print("=== Case 3: SurvivalArena (one switch -> two doors) ===")
        arena = by_id.get("survival_arena") or {}
        arena_report = evidence.verify_contract(arena, project, godot, replay=2,
                                               timeout_s=120,
                                               run_id=evidence._new_run_id("arena"))
        ok("case3: the arena chain PASSes", arena_report.status == evidence.STATUS_PASS,
           "%s | %s" % (arena_report.status, arena_report.detail))
        ok("case3: both doors were closed before the switch and open after it",
           check_for(arena_report, "both_doors_start_closed",
                     "Mechanism/MainDoor").get("observed") is False
           and check_for(arena_report, "reward_switch_opens_both_doors",
                         "Mechanism/MainDoor").get("observed") is True
           and check_for(arena_report, "reward_switch_opens_both_doors",
                         "Mechanism/SideDoor").get("observed") is True)
        ok("case3: each door emitted exactly one open event",
           [check.get("observed") for check in arena_report.checks
            if check.get("stage") == "reward_switch_opens_both_doors"
            and check.get("check") == "signal"] == [1, 1])
        ok("case3: two replays agree", arena_report.replay_consistent)
        ok("case3: the arena chain is two stages (not a single behaviour)",
           arena_report.stage_count == 2)

        # ---------------- Case 4: 非法契约 ----------------
        print("=== Case 4: invalid composite contracts are rejected ===")

        def expect_invalid(name: str, mutate, needle: str) -> None:
            contract, errors = contract_from(base_raw, mutate)
            ok("case4: %s is INVALID" % name,
               contract is None and any(needle in message for message in errors),
               "; ".join(errors)[:300])

        expect_invalid("unknown scene id", lambda raw: raw.update(scene_id="ghost_room"),
                       "does not match the file name")
        expect_invalid("scene path mismatch",
                       lambda raw: raw.update(scene="Scenes/SurvivalArena.tscn"),
                       "must be exactly")
        expect_invalid("denied action",
                       lambda raw: raw["stages"][0]["actions"].append(
                           {"type": "state.set_property",
                            "target": "Mechanism/ExitDoor",
                            "params": {"property": "trigger_switch.trigger_mode",
                                       "value": "Toggle"}}),
                       "denies")
        expect_invalid("single stage",
                       lambda raw: raw.update(stages=raw["stages"][:1]), "outside limits")
        expect_invalid("zero-frame negative-only stage",
                       lambda raw: raw["stages"][0].update(
                           actions=[{"type": "input.press",
                                     "params": {"action": "move_right"}}],
                           expected=[{"check": "door.is_open",
                                      "target": "Mechanism/ExitDoor", "equals": False}]),
                       "without any observation window")
        expect_invalid("unknown observation",
                       lambda raw: raw["stages"][0]["expected"].append(
                           {"check": "gate.is_open", "target": "Mechanism/ConditionGate",
                            "equals": True}),
                       "not a registered check")
        expect_invalid("target path escape",
                       lambda raw: raw["stages"][0]["expected"].append(
                           {"check": "door.is_open", "target": "../Mechanism/ExitDoor",
                            "equals": False}),
                       "not a scene path")
        expect_invalid("window out of range",
                       lambda raw: raw["stages"][0].update(window_frames=0),
                       "window_frames must be 1..")
        expect_invalid("frame budget exceeded",
                       lambda raw: raw["stages"][0].update(
                           actions=[{"type": "simulation.advance_frames",
                                     "params": {"frames": 300}},
                                    {"type": "simulation.advance_frames",
                                     "params": {"frames": 300}},
                                    {"type": "simulation.advance_frames",
                                     "params": {"frames": 300}},
                                    {"type": "simulation.advance_frames",
                                     "params": {"frames": 300}},
                                    {"type": "simulation.advance_frames",
                                     "params": {"frames": 300}}]),
                       "exceeds max_total_frames")
        expect_invalid("duplicate stage id",
                       lambda raw: raw["stages"][1].update(id=raw["stages"][0]["id"]),
                       "duplicate stage id")
        expect_invalid("unknown feature", lambda raw: raw.update(features=["ghost_feature"]),
                       "unknown Features")
        expect_invalid("unknown contract key", lambda raw: raw.update(expectations=[]),
                       "unknown keys")

        # ---------------- Case 5: 断开关键连接 ----------------
        print("=== Case 5: a broken switch->gate connection fails the chain ===")
        scene_path = os.path.join(project, ESCAPE_SCENE)
        scene_bytes = read_bytes(scene_path)
        ok("case5: the fixture starts from a scene with the switch B connection",
           SWITCH_LINK.encode() in scene_bytes)
        write_bytes(scene_path, scene_bytes.replace(SWITCH_LINK.encode(), b""))
        broken = evidence.verify_contract(escape, project, godot, replay=1, timeout_s=120,
                                         run_id=evidence._new_run_id("broken_link"))
        write_bytes(scene_path, scene_bytes)
        ok("case5: the scene copy is restored byte-for-byte",
           sha256(scene_path) == hashlib.sha256(scene_bytes).hexdigest())
        ok("case5: the chain no longer PASSes", broken.status != evidence.STATUS_PASS,
           broken.status)
        ok("case5: it fails exactly at the second-switch stage",
           broken.failed_stage == "switch_b_fulfils_gate_and_opens_door",
           str(broken.failed_stage))
        ok("case5: the first two stages are recorded as completed",
           broken.completed_stages == ["closed_door_blocks_traversal",
                                       "switch_a_partial_condition_keeps_door_closed"],
           str(broken.completed_stages))
        ok("case5: the failure names the gate observation, not a missing node",
           check_for(broken, "switch_b_fulfils_gate_and_opens_door",
                     "Mechanism/ConditionGate").get("observed") is False
           and broken.reason == "state_mismatch",
           "%s / %s" % (broken.reason, broken.detail))

        # ---------------- Case 6: 门报告已开但仍阻挡 ----------------
        print("=== Case 6: an opened door that still blocks fails the traversal ===")
        script_path = os.path.join(project, DOOR_SCRIPT)
        script_bytes = read_bytes(script_path)
        script_text = script_bytes.decode("utf-8")
        ok("case6: the fixture contains the collision release branch",
           DOOR_COLLISION_BLOCK in script_text)
        write_bytes(script_path, script_text.replace(
            DOOR_COLLISION_BLOCK,
            "\tif _collision != null:\n\t\t_collision.set_deferred(\"disabled\", false)\n"
        ).encode("utf-8"))
        stuck = evidence.verify_contract(escape, project, godot, replay=1, timeout_s=120,
                                        run_id=evidence._new_run_id("stuck_door"))
        write_bytes(script_path, script_bytes)
        ok("case6: the door script is restored byte-for-byte",
           sha256(script_path) == hashlib.sha256(script_bytes).hexdigest())
        ok("case6: the chain no longer PASSes", stuck.status != evidence.STATUS_PASS,
           stuck.status)
        ok("case6: is_open alone is not enough to pass", check_for(
            stuck, "switch_b_fulfils_gate_and_opens_door",
            "Mechanism/ExitDoor").get("observed") is True)
        ok("case6: the traversal stage is the one that fails",
           stuck.failed_stage == "player_traverses_opened_gap", str(stuck.failed_stage))
        ok("case6: the player is still on the closed side of the door",
           (check_for(stuck, "player_traverses_opened_gap", "Player").get("observed")
            or 0.0) < 384.0,
           str(check_for(stuck, "player_traverses_opened_gap", "Player")))
        ok("case6: three stages are recorded as completed",
           stuck.completed_stages == [
               "closed_door_blocks_traversal",
               "switch_a_partial_condition_keeps_door_closed",
               "switch_b_fulfils_gate_and_opens_door"],
           str(stuck.completed_stages))

        # ---------------- Case 7: 观测不可用 ----------------
        print("=== Case 7: an unavailable observation target is INSUFFICIENT ===")
        unavailable, errors = contract_from(base_raw, lambda raw: raw["stages"][1][
            "expected"].__setitem__(2, {"check": "gate.is_fulfilled",
                                        "target": "Mechanism/MissingGate",
                                        "equals": False}))
        ok("case7: the mutated contract is still valid", errors == [], "; ".join(errors))
        missing = evidence.verify_contract(unavailable, project, godot, replay=1,
                                          timeout_s=120,
                                          run_id=evidence._new_run_id("missing"))
        ok("case7: the result is INSUFFICIENT / check_unavailable",
           missing.status == evidence.STATUS_INSUFFICIENT
           and missing.reason == "check_unavailable",
           "%s / %s" % (missing.status, missing.reason))
        ok("case7: it is never reported as PASS", missing.status != evidence.STATUS_PASS)
        ok("case7: the failing stage is recorded",
           missing.failed_stage == "switch_a_partial_condition_keeps_door_closed",
           str(missing.failed_stage))

        # ---------------- Case 8: 前置条件不满足 ----------------
        print("=== Case 8: an unmet precondition stops before any action ===")
        unmet, errors = contract_from(base_raw, lambda raw: raw["preconditions"][0].update(
            equals=True))
        ok("case8: the mutated contract is still valid", errors == [], "; ".join(errors))
        blocked_run = evidence.verify_contract(unmet, project, godot, replay=1,
                                              timeout_s=120,
                                              run_id=evidence._new_run_id("precondition"))
        ok("case8: INSUFFICIENT / precondition_unmet",
           blocked_run.status == evidence.STATUS_INSUFFICIENT
           and blocked_run.reason == "precondition_unmet",
           "%s / %s" % (blocked_run.status, blocked_run.reason))
        ok("case8: no stage ran and no action was executed",
           blocked_run.completed_stages == [] and not blocked_run.runs[0]["action_executed"],
           json.dumps(blocked_run.runs[0].get("stages"))[:200])

        # ---------------- Case 9: 中间状态预期错误 ----------------
        print("=== Case 9: a wrong intermediate expectation stops the chain ===")
        wrong, errors = contract_from(base_raw, lambda raw: raw["stages"][1][
            "expected"].__setitem__(2, {"check": "gate.is_fulfilled",
                                        "target": "Mechanism/ConditionGate",
                                        "equals": True}))
        ok("case9: the mutated contract is still valid", errors == [], "; ".join(errors))
        refused = evidence.verify_contract(wrong, project, godot, replay=1, timeout_s=120,
                                          run_id=evidence._new_run_id("wrong_expectation"))
        ok("case9: the chain reports MISMATCH at that stage",
           refused.status == evidence.STATUS_MISMATCH
           and refused.failed_stage == "switch_a_partial_condition_keeps_door_closed",
           "%s / %s" % (refused.status, refused.failed_stage))
        ok("case9: later stages never ran",
           refused.completed_stages == ["closed_door_blocks_traversal"]
           and len(refused.runs[0].get("stages") or []) == 2,
           str(refused.completed_stages))
        ok("case9: the traversal stage is absent from the evidence",
           "player_traverses_opened_gap" not in refused.completed_stages)

        # ---------------- Case 10: 探针层零帧门禁 ----------------
        print("=== Case 10: the probe rejects a zero-frame absence-only stage ===")
        zero_contract = {
            "scene_id": "escape_room",
            "scene": "res://Scenes/EscapeRoom.tscn",
            "run_id": "zero-window-1",
            "replay_index": 1,
            "preconditions": [],
            "stages": [
                {"id": "no_window",
                 "actions": [{"type": "input.press", "target": ".",
                              "params": {"action": "move_right"}}],
                 "expected": [{"check": "door.is_open", "target": "Mechanism/ExitDoor",
                               "equals": False}],
                 "window_frames": 5},
                {"id": "after",
                 "actions": [{"type": "simulation.advance_frames", "target": ".",
                              "params": {"frames": 12}}],
                 "expected": [{"check": "trigger.is_triggered",
                               "target": "Mechanism/SwitchA", "equals": False}],
                 "window_frames": 5},
            ],
        }
        payload = evidence.run_probe(zero_contract, project, godot, timeout_s=60) \
            .get("result") or {}
        ok("case10: the probe returns INVALID / contract_invalid",
           payload.get("status") == "INVALID" and payload.get("reason") == "contract_invalid",
           json.dumps(payload)[:300])
        ok("case10: the detail names the missing observation window",
           "observation window" in str(payload.get("detail", "")),
           str(payload.get("detail")))
        escaped_path = dict(zero_contract)
        escaped_path["scene"] = "res://Scenes/../project.godot"
        payload = evidence.run_probe(escaped_path, project, godot, timeout_s=60) \
            .get("result") or {}
        ok("case10: an unlisted scene path is rejected before loading",
           payload.get("status") == "INVALID"
           and "allowlist" in str(payload.get("detail", "")),
           json.dumps(payload)[:300])

        # ---------------- Case 11: 重放不一致 ----------------
        print("=== Case 11: inconsistent replays never stay PASS ===")

        def payload_for(status: str, failed: str = None) -> dict:
            """与真实契约同形的合成观测：四个阶段、每段都有检查。"""
            stage_ids = [stage["id"] for stage in contract["stages"]]
            passing_check = {"check": "door.is_open", "target": "Mechanism/ExitDoor",
                             "entry": "", "expected": False, "observed": False,
                             "status": "PASS", "first_observed_frame": 0}
            stages = []
            for stage_id in stage_ids:
                stage_status = "PASS"
                if stage_id == failed:
                    stage_status = "MISMATCH"
                stage_check = dict(passing_check)
                if stage_status != "PASS":
                    stage_check["status"] = "STATE_MISMATCH"
                    stage_check["observed"] = True
                stages.append({"id": stage_id, "status": stage_status, "reason": "",
                               "checks": [stage_check]})
            return {"status": status,
                    "reason": "ok" if status == "PASS" else "state_mismatch",
                    "detail": "", "action_executed": True,
                    "completed_stages": [] if failed else stage_ids,
                    "failed_stage": failed, "stages": stages,
                    "checks": [check for stage in stages for check in stage["checks"]]}

        calls = {"n": 0}

        def alternating_runner(attempt, project_root="", timeout_s=0, godot=""):
            calls["n"] += 1
            payload = payload_for("PASS") if calls["n"] == 1 else payload_for(
                "MISMATCH", "switch_a_partial_condition_keeps_door_closed")
            return {"result": payload, "stdout": "", "stderr": "", "exit_code": 0,
                    "duration": 0.0, "timed_out": False, "artifacts": {}}

        inconsistent = evidence.verify_contract(contract, project, godot, replay=2,
                                              timeout_s=60, runner=alternating_runner,
                                              run_id="replay-test")
        ok("case11: a PASS that is not reproducible is downgraded",
           inconsistent.status == evidence.STATUS_INSUFFICIENT
           and inconsistent.reason == "replay_inconsistent",
           "%s / %s" % (inconsistent.status, inconsistent.reason))
        ok("case11: the inconsistency is reported as such", not inconsistent.replay_consistent)

        # ---------------- Case 12: CLI ----------------
        print("=== Case 12: CLI exit codes ===")
        code, output = run_cli(["--scene", "escape_room", "--replay", "1"])
        ok("case12: a passing chain exits 0", code == 0, output[-300:])
        ok("case12: the CLI reports the workspace was cleaned up",
           "workspace removed=True" in output, output[-300:])

        bad_dir = os.path.join(DOTAI, "tmp", "composite_bad_contracts")
        os.makedirs(bad_dir, exist_ok=True)
        bad_raw = copy.deepcopy(base_raw)
        bad_raw["stages"][1]["expected"][2]["equals"] = True
        write_text(os.path.join(bad_dir, "escape_room.yaml"),
                   yaml.safe_dump(bad_raw, sort_keys=False, allow_unicode=True))
        code, output = run_cli(["--scene", "escape_room", "--replay", "1",
                                "--contracts-dir", bad_dir, "--project-root", project])
        ok("case12: a MISMATCH exits 1", code == 1, output[-300:])
        ok("case12: the CLI reports the failing stage",
           "switch_a_partial_condition_keeps_door_closed" in output, output[-400:])
        ok("case12: a failing run still cleans its workspace",
           "workspace removed=True" in output, output[-300:])

        invalid_dir = os.path.join(DOTAI, "tmp", "composite_invalid_contracts")
        os.makedirs(invalid_dir, exist_ok=True)
        invalid_raw = copy.deepcopy(base_raw)
        invalid_raw["scene"] = "Scenes/SurvivalArena.tscn"
        write_text(os.path.join(invalid_dir, "escape_room.yaml"),
                   yaml.safe_dump(invalid_raw, sort_keys=False, allow_unicode=True))
        code, output = run_cli(["--scene", "escape_room", "--replay", "1",
                                "--contracts-dir", invalid_dir])
        ok("case12: an invalid contract exits 1", code == 1, output[-300:])
        ok("case12: the invalid contract is reported as INVALID",
           "invalid=1" in output, output[-300:])

        code, output = run_cli(["--scene", "escape_room", "--replay", "1",
                                "--godot", os.path.join(DOTAI, "tmp", "no-godot")])
        ok("case12: a missing Godot is INSUFFICIENT (exit 0 by default)", code == 0,
           output[-300:])
        code, output = run_cli(["--scene", "escape_room", "--replay", "1",
                                "--godot", os.path.join(DOTAI, "tmp", "no-godot"),
                                "--require-composite"])
        ok("case12: --require-composite turns INSUFFICIENT into exit 1", code == 1,
           output[-300:])

        # ---------------- Case 13: 资源所有权 ----------------
        print("=== Case 13: generated resources are cleaned only when owned ===")
        owned_dir = workspace.root
        cleanup = workspace.close()
        ok("case13: the owned workspace is removed", cleanup["removed"] is True,
           json.dumps(cleanup))
        ok("case13: the workspace directory is gone", not os.path.isdir(owned_dir))

        foreign_run = "999-%s" % ("f" * 10)
        foreign = os.path.join(EVIDENCE_ROOT_WORKSPACES, foreign_run)
        os.makedirs(foreign, exist_ok=True)
        write_text(os.path.join(foreign, evidence.OWNER_FILE),
                   json.dumps({"run_id": foreign_run}))
        write_text(os.path.join(foreign, "keep.txt"), "not ours to delete\n")
        fake = evidence.CompositeWorkspace.__new__(evidence.CompositeWorkspace)
        fake.run_id = "other-run"
        fake.root = foreign
        refused = fake.close()
        ok("case13: a workspace owned by another run is not deleted",
           refused["removed"] is False and os.path.isdir(foreign),
           json.dumps(refused))
        ok("case13: the refusal names the ownership record",
           "owner.json belongs to" in refused["kept_reason"], refused["kept_reason"])
        ok("case13: foreign content is untouched",
           read_text(os.path.join(foreign, "keep.txt")).startswith("not ours"))
        ok("case13: stale workspaces are reported",
           any(entry["path"] == foreign for entry in
               evidence.CompositeWorkspace.stale_workspaces()))
        shutil.rmtree(foreign, ignore_errors=True)

        crash = evidence.CompositeWorkspace(evidence._new_run_id("crash"), "", 60,
                                            PROJECT_ROOT)
        crash_dir = crash.root
        try:
            raise RuntimeError("simulated chain failure")
        except RuntimeError:
            crash_cleanup = crash.close()
        ok("case13: an interrupted run still cleans its own workspace",
           crash_cleanup["removed"] is True and not os.path.isdir(crash_dir),
           json.dumps(crash_cleanup))
        ok("case13: a fresh workspace refuses to take over an existing directory",
           _rejects_duplicate(crash_dir, evidence, PROJECT_ROOT))
    finally:
        if os.path.isdir(workspace.root):
            ws_cleanup = workspace.close()
            ok("teardown: the test workspace is removed", ws_cleanup["removed"] is True,
               json.dumps(ws_cleanup))

    # ---------------- Case 14: 仓库保护 ----------------
    print("=== Case 14: repository files are untouched ===")
    ok("case14: no golden scene / script / contract changed",
       snapshot(REPO_PROTECTED) == repo_hashes,
       str({path: (repo_hashes[path], sha256(os.path.join(PROJECT_ROOT, path)))
            for path in REPO_PROTECTED
            if repo_hashes[path] != sha256(os.path.join(PROJECT_ROOT, path))}))
    ok("case14: the repo manifest still matches the protocol",
       composite_protocol.check_manifest(composite_protocol.load_protocol()) == [])
    ok("case14: the behaviour manifest still matches its protocol",
       behavior_protocol.check_manifest(behavior_protocol.load_protocol()) == [])

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: all composite behavior evidence checks passed")
    return 0


EVIDENCE_ROOT_WORKSPACES = os.path.join(evidence.EVIDENCE_ROOT, "workspaces")


def _rejects_duplicate(path: str, module, root: str) -> bool:
    """同名工作区目录已存在时必须拒绝接管（而不是复用他人目录）。"""
    os.makedirs(path, exist_ok=True)
    try:
        module.CompositeWorkspace(os.path.basename(path), "", 60, root)
    except OSError:
        return True
    finally:
        shutil.rmtree(path, ignore_errors=True)
    return False


if __name__ == "__main__":
    sys.exit(main())
