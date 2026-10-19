#!/usr/bin/env python3
"""Trace replay unit tests（Phase 1.22）。

人工构造事件序列覆盖回放器契约（真实 Godot 运行产生的 trace 由
`Tests/test_orchestration_trace.gd` 与 E2E P 段覆盖，不在本文件伪造）。

用法: python .ai/tools/validator/tests/test_orchestration_trace.py
退出码: 0 = 全部通过；1 = 有失败。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_TOOLS = Path(__file__).resolve().parents[2]              # .ai/tools
sys.path.insert(0, str(_TOOLS / "validator"))

import trace_replay                                        # noqa: E402

_failures: list[str] = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + ((" | " + detail) if detail else ""))


def event(sequence, event_type, *, reason="code", stage_id=None, stage_index=None,
          timestamp=None, source="orchestrator", run_id="run-test", data=None,
          **extra):
    record = {
        "schema_version": 1,
        "run_id": run_id,
        "sequence": sequence,
        "event_type": event_type,
        "timestamp_ms": sequence if timestamp is None else timestamp,
        "stage_id": stage_id,
        "stage_index": stage_index,
        "source": source,
        "reason": reason,
        "entity_id": None,
        "instance_name": None,
        "data": {} if data is None else data,
    }
    record.update(extra)
    return record


def started(mode="boss", stage_count=0, **extra):
    return event(0, "orchestration_started", reason=mode,
                 data={"mode": mode, "stage_count": stage_count}, **extra)


def stage_started(sequence, index, stage_id, stage_type="clear_enemies"):
    return event(sequence, "stage_started", reason=stage_type, stage_id=stage_id,
                 stage_index=index, data={"stage_type": stage_type})


def stage_completed(sequence, index, stage_id, stage_type="clear_enemies"):
    return event(sequence, "stage_completed", reason=stage_type, stage_id=stage_id,
                 stage_index=index, data={"stage_type": stage_type})


def transition(sequence, from_index, from_id, to_index, to_id, reason="stage_completed"):
    return event(sequence, "stage_transitioned", reason=reason, stage_id=to_id,
                 stage_index=to_index,
                 data={"from_stage_id": from_id, "from_stage_index": from_index,
                       "to_stage_id": to_id, "to_stage_index": to_index})


def boss_death_confirmed(sequence):
    return event(sequence, "boss_death_confirmed", reason="health_died",
                 entity_id="boss", instance_name="Boss")


def document(events, *, run_id="run-test", event_count=None, dropped=0,
             schema=1):
    return {
        "document": "orchestration_trace",
        "schema_version": schema,
        "run_id": run_id,
        "config_path": "res://Levels/test.json",
        "event_count": len(events) if event_count is None else event_count,
        "dropped_events": dropped,
        "events": events,
    }


def two_stage_events(final="victory"):
    events = [
        started("boss", 2),
        stage_started(1, 0, "clear_1"),
        stage_completed(2, 0, "clear_1"),
        transition(3, 0, "clear_1", 1, "boss"),
        stage_started(4, 1, "boss", "defeat_boss"),
        boss_death_confirmed(5),
        stage_completed(6, 1, "boss", "defeat_boss"),
        transition(7, 1, "boss", None, None, reason="stages_exhausted"),
    ]
    if final == "victory":
        events.append(event(8, "level_victory", reason="boss_defeated"))
    elif final == "failed":
        events.append(event(8, "level_failed", reason="player_died"))
    return events


def errors_reasons(result) -> list:
    return [error["reason"] for error in result["errors"]]


def run() -> int:
    # ---------- 契约与状态重建 ----------
    good = trace_replay.replay_document(document(two_stage_events()))
    ok("R1: a valid two-stage boss trace replays to victory",
       good["ok"] and good["final_state"] == "victory"
       and good["mode"] == "boss" and good["boss_death_confirmed"]
       and good["victory"] and not good["failed"] and good["terminated"])
    ok("R2: stages and transitions are reconstructed in declared order",
       [(s["stage_id"], s["stage_index"]) for s in good["started_stages"]]
       == [("clear_1", 0), ("boss", 1)]
       and [(s["stage_id"], s["stage_index"]) for s in good["completed_stages"]]
       == [("clear_1", 0), ("boss", 1)]
       and good["transitions"][0] == {"sequence": 3, "from": "clear_1", "from_index": 0,
                                      "to": "boss", "to_index": 1,
                                      "reason": "stage_completed"}
       and good["transitions"][1]["to"] is None,
       repr(good["transitions"]))
    ok("R3: current stage reports the final stage identity",
       good["current_stage_id"] == "boss" and good["current_stage_index"] == 1)
    ok("R4: event summary counts each type once",
       good["event_summary"].get("level_victory") == 1
       and good["event_summary"].get("stage_started") == 2
       and good["event_summary"].get("boss_death_confirmed") == 1,
       repr(good["event_summary"]))
    ok("R5: a failed two-stage trace replays to failed",
       trace_replay.replay_document(document(two_stage_events("failed")))["final_state"]
       == "failed")
    ok("R6: an in-progress trace has no terminal state and reports playing",
       trace_replay.replay_document(
           document([started("boss", 2), stage_started(1, 0, "clear_1")]))["final_state"]
       == "playing")
    single = [started("boss", 0), boss_death_confirmed(1),
              event(2, "level_victory", reason="boss_defeated")]
    single_result = trace_replay.replay_document(document(single))
    ok("R7: single-stage boss trace (no stage events) is accepted",
       single_result["ok"] and single_result["final_state"] == "victory"
       and not single_result["started_stages"])
    ignored_trace = trace_replay.replay_document(document(
        [started("boss", 0), boss_death_confirmed(1),
         event(2, "level_victory", reason="boss_defeated"),
         event(3, "duplicate_event_ignored", reason="boss_death")]))
    ok("R8: duplicate notifications after terminal are collected, not errors",
       ignored_trace["ok"] and len(ignored_trace["ignored_events"]) == 1
       and ignored_trace["ignored_events"][0]["reason"] == "boss_death")
    rejected_trace = trace_replay.replay_document(document(
        [started("boss", 2), stage_started(1, 0, "clear_1"),
         event(2, "invalid_transition_rejected", reason="victory_blocked")]))
    ok("R9: rejected transitions are surfaced with stable reason codes",
       rejected_trace["rejected_events"] == [{"sequence": 2, "reason": "victory_blocked"}])

    # ---------- 文档 / 输入契约 ----------
    round_trip = json.loads(json.dumps(document(two_stage_events())))
    ok("R10: serialized trace round-trips to the same replay result",
       trace_replay.replay_document(round_trip) == good)
    ok("R11: unknown document schema version is rejected",
       "unsupported_schema_version" in errors_reasons(
           trace_replay.replay_document(document(two_stage_events(), schema=99))))
    bad_event_version = two_stage_events()
    bad_event_version[2]["schema_version"] = 2
    ok("R12: unknown event schema version is rejected",
       "unsupported_schema_version" in errors_reasons(
           trace_replay.replay_document(document(bad_event_version))))
    ok("R13: unknown event type is rejected (not silently ignored)",
       "unknown_event_type" in errors_reasons(trace_replay.replay_document(
           document([started("boss", 0), event(1, "teleported")]))))
    missing = [started("boss", 0), boss_death_confirmed(1),
               event(2, "level_victory", reason="boss_defeated")]
    del missing[2]["reason"]  # noqa: E501 - 显式构造缺字段事件
    ok("R14: missing required fields are rejected with the field list",
       "missing_field" in errors_reasons(trace_replay.replay_document(document(missing))))
    bad_data = [started("boss", 0), event(1, "level_victory", reason="x", data=[1, 2])]
    ok("R15: non-object data is rejected",
       "invalid_field" in errors_reasons(trace_replay.replay_document(document(bad_data))))
    ok("R16: empty trace is rejected explicitly",
       errors_reasons(trace_replay.replay_document(document([]))) == ["empty_trace"])
    ok("R17: event_count mismatch is reported as truncated",
       "truncated_trace" in errors_reasons(trace_replay.replay_document(
           document(two_stage_events(), event_count=99))))
    ok("R18: dropped recorder events mark the trace incomplete",
       "trace_incomplete" in errors_reasons(trace_replay.replay_document(
           document(two_stage_events(), dropped=2))))
    ok("R19: run_id mismatch is rejected",
       "run_id_mismatch" in errors_reasons(trace_replay.replay_document(
           document(two_stage_events(), run_id="other-run"))))

    # ---------- 序号 / 时间戳 ----------
    duplicate_sequence = [started("boss", 0), boss_death_confirmed(1),
                          event(1, "level_victory", reason="boss_defeated")]
    ok("R20: duplicate sequence numbers are rejected",
       "sequence_not_increasing" in errors_reasons(
           trace_replay.replay_document(document(duplicate_sequence))))
    backwards = [started("boss", 0), boss_death_confirmed(2),
                 event(1, "level_victory", reason="boss_defeated")]
    ok("R21: sequence regression is rejected",
       "sequence_not_increasing" in errors_reasons(
           trace_replay.replay_document(document(backwards))))
    gap = [started("boss", 0), boss_death_confirmed(2),
           event(3, "level_victory", reason="boss_defeated")]
    gap_result = trace_replay.replay_document(document(gap))
    ok("R22: sequence gaps are rejected as missing events",
       "sequence_gap" in errors_reasons(gap_result) and gap_result["sequence_gaps"] == 1)
    regressed_time = two_stage_events()
    regressed_time[3]["timestamp_ms"] = 100
    regressed_time[4]["timestamp_ms"] = 1
    ok("R23: regressed timestamps are rejected",
       "timestamp_regressed" in errors_reasons(
           trace_replay.replay_document(document(regressed_time))))
    same_time = two_stage_events()
    for item in same_time:
        item["timestamp_ms"] = 0
    same_result = trace_replay.replay_document(document(same_time))
    ok("R24: equal timestamps are ordered deterministically by sequence",
       same_result["ok"] and same_result["final_state"] == "victory")
    ok("R25: replaying the same trace twice returns identical results",
       json.dumps(same_result, sort_keys=True)
       == json.dumps(trace_replay.replay_document(document(same_time)), sort_keys=True))

    # ---------- 状态机约束 ----------
    skipped = [started("boss", 2), stage_started(1, 1, "boss", "defeat_boss")]
    ok("R26: entering the boss stage before clearing enemies is rejected",
       "stage_start_out_of_order" in errors_reasons(
           trace_replay.replay_document(document(skipped))))
    two_active = [started("boss", 2), stage_started(1, 0, "clear_1"),
                  stage_started(2, 1, "boss", "defeat_boss")]
    ok("R27: starting a new stage before completing the active one is rejected",
       "stage_start_before_completion" in errors_reasons(
           trace_replay.replay_document(document(two_active))))
    no_start = [started("boss", 2), stage_completed(1, 0, "clear_1")]
    ok("R28: completing an unstarted stage is rejected",
       "stage_completed_without_start" in errors_reasons(
           trace_replay.replay_document(document(no_start))))
    mismatch = [started("boss", 2), stage_started(1, 0, "clear_1"),
                stage_completed(2, 1, "clear_1")]
    ok("R29: mismatched stage completion is rejected",
       "stage_completed_mismatch" in errors_reasons(
           trace_replay.replay_document(document(mismatch))))
    double_complete = [started("boss", 2),
                       stage_started(1, 0, "clear_1"),
                       stage_completed(2, 0, "clear_1"),
                       transition(3, 0, "clear_1", 1, "boss"),
                       stage_started(4, 1, "boss", "defeat_boss"),
                       stage_completed(5, 1, "boss", "defeat_boss"),
                       stage_completed(6, 1, "boss", "defeat_boss")]
    ok("R30: duplicate stage completion is rejected",
       "duplicate_stage_completion" in errors_reasons(
           trace_replay.replay_document(document(double_complete))))
    wrong_source = [started("boss", 2), stage_started(1, 0, "clear_1"),
                    stage_completed(2, 0, "clear_1"),
                    transition(3, 1, "boss", 1, "boss")]
    ok("R31: transitions must come from the last completed stage",
       "transition_source_mismatch" in errors_reasons(
           trace_replay.replay_document(document(wrong_source))))
    premature_victory = [started("boss", 2), stage_started(1, 0, "clear_1"),
                         boss_death_confirmed(2),
                         event(3, "level_victory", reason="boss_defeated")]
    ok("R32: victory before every declared stage completes is rejected",
       "victory_before_all_stages" in errors_reasons(
           trace_replay.replay_document(document(premature_victory))))
    no_boss_death = [started("boss", 2), stage_started(1, 0, "clear_1"),
                     stage_completed(2, 0, "clear_1"),
                     transition(3, 0, "clear_1", 1, "boss"),
                     stage_started(4, 1, "boss", "defeat_boss"),
                     stage_completed(5, 1, "boss", "defeat_boss"),
                     transition(6, 1, "boss", None, None, reason="stages_exhausted"),
                     event(7, "level_victory", reason="boss_defeated")]
    ok("R33: boss-mode victory without confirmed boss death is rejected",
       "victory_without_boss_death" in errors_reasons(
           trace_replay.replay_document(document(no_boss_death))))
    two_boss_deaths = [started("boss", 0), boss_death_confirmed(1),
                       boss_death_confirmed(2)]
    ok("R34: duplicate boss death confirmation is rejected",
       "duplicate_boss_death" in errors_reasons(
           trace_replay.replay_document(document(two_boss_deaths))))
    after_terminal = two_stage_events()
    after_terminal.append(stage_started(9, 0, "clear_1"))
    ok("R35: stage transitions after a terminal event are rejected",
       "event_after_terminal" in errors_reasons(
           trace_replay.replay_document(document(after_terminal))))
    conflicting = two_stage_events()
    conflicting.append(event(9, "level_failed", reason="player_died"))
    ok("R36: victory and failure in the same trace are rejected",
       "conflicting_terminal" in errors_reasons(
           trace_replay.replay_document(document(conflicting))))
    duplicate_terminal = two_stage_events()
    duplicate_terminal.append(event(9, "level_victory", reason="boss_defeated"))
    ok("R37: a second terminal event of the same type is rejected",
       "duplicate_terminal" in errors_reasons(
           trace_replay.replay_document(document(duplicate_terminal))))
    missing_start = [stage_started(0, 0, "clear_1")]
    ok("R38: traces without orchestration_started are rejected",
       "missing_start" in errors_reasons(
           trace_replay.replay_document(document(missing_start))))
    boss_in_waves = [started("waves", 0), boss_death_confirmed(1)]
    ok("R39: boss death outside boss mode is rejected",
       "boss_death_outside_boss_mode" in errors_reasons(
           trace_replay.replay_document(document(boss_in_waves))))
    waves_victory = [started("waves", 0), event(1, "level_victory", reason="all_waves_cleared")]
    ok("R40: waves victory does not require a boss death",
       trace_replay.replay_document(document(waves_victory))["ok"])

    # ---------- CLI ----------
    with tempfile.TemporaryDirectory() as tmp:
        good_path = Path(tmp) / "good.trace.json"
        good_path.write_text(json.dumps(document(two_stage_events())), encoding="utf-8")
        cli_ok = trace_replay.main([str(good_path), "--json"])
        bad_path = Path(tmp) / "bad.trace.json"
        bad_path.write_text(json.dumps(document(backwards)), encoding="utf-8")
        cli_bad = trace_replay.main([str(bad_path)])
        missing_path = Path(tmp) / "missing.trace.json"
        cli_missing = trace_replay.main([str(missing_path)])
        not_json = Path(tmp) / "not-json.trace.json"
        not_json.write_text("{not json", encoding="utf-8")
        cli_not_json = trace_replay.main([str(not_json)])
    ok("R41: CLI returns 0 for a valid trace", cli_ok == 0)
    ok("R42: CLI returns 1 for a contract-violating trace", cli_bad == 1)
    ok("R43: CLI returns 2 for a missing or unreadable trace",
       cli_missing == 2 and cli_not_json == 2)

    # ==================== Phase 1.25：waves 语义事件回放规则 ====================
    print()
    print("--- R44+. wave semantic events (Phase 1.25) ---")

    def wave_started(sequence, wave, total, enemies=1):
        return event(sequence, "wave_started", reason="wave_begin",
                     data={"wave": wave, "total": total, "enemies": enemies})

    def wave_cleared(sequence, wave):
        return event(sequence, "wave_cleared", reason="wave_cleared",
                     data={"wave": wave})

    def exit_unlocked(sequence, wave):
        return event(sequence, "exit_unlocked", reason="all_waves_cleared",
                     data={"wave": wave})

    def waves_document(events):
        return document(events)

    # 合法完整序列（exit_reached 路径，与真实 waves 捕获一致）
    legal = [
        started("waves", 0),
        wave_started(1, 0, 2, 1),
        wave_cleared(2, 0),
        wave_started(3, 1, 2, 2),
        wave_cleared(4, 1),
        exit_unlocked(5, 1),
        event(6, "level_victory", reason="exit_reached_after_unlock"),
    ]
    r = trace_replay.replay_document(waves_document(legal))
    ok("R44: a legal full waves trace replays to victory",
       r["ok"] and r["final_state"] == "victory", repr(r["errors"][:2]))

    # all_waves_cleared 直接胜利路径（无 exit_unlocked）
    direct = [
        started("waves", 0),
        wave_started(1, 0, 1, 2),
        wave_cleared(2, 0),
        event(3, "level_victory", reason="all_waves_cleared"),
    ]
    r = trace_replay.replay_document(waves_document(direct))
    ok("R45: the all_waves_cleared victory path needs no exit_unlocked",
       r["ok"] and r["final_state"] == "victory", repr(r["errors"][:2]))

    # 前一波未清空时提前推进
    premature = [
        started("waves", 0),
        wave_started(1, 0, 2, 1),
        wave_started(2, 1, 2, 2),
        wave_cleared(3, 1),
        wave_cleared(4, 0),
        exit_unlocked(5, 1),
        event(6, "level_victory", reason="exit_reached_after_unlock"),
    ]
    r = trace_replay.replay_document(waves_document(premature))
    ok("R46: starting the next wave before the current one is cleared is rejected"
       " (order constraint)",
       not r["ok"] and "wave_start_before_clear" in errors_reasons(r),
       repr(errors_reasons(r)[:3]))

    # 跳过 wave_started / 波次索引跳跃
    skip = [
        started("waves", 0),
        wave_started(1, 0, 3, 1),
        wave_cleared(2, 0),
        wave_started(3, 2, 3, 1),
    ]
    r = trace_replay.replay_document(waves_document(skip))
    ok("R47: a skipped wave index is rejected (wave_start_out_of_order)",
       not r["ok"] and "wave_start_out_of_order" in errors_reasons(r),
       repr(errors_reasons(r)[:3]))

    # 重复记录波次清空
    dup_clear = [
        started("waves", 0),
        wave_started(1, 0, 1, 1),
        wave_cleared(2, 0),
        wave_cleared(3, 0),
        event(4, "level_victory", reason="all_waves_cleared"),
    ]
    r = trace_replay.replay_document(waves_document(dup_clear))
    ok("R48: a duplicate wave_cleared is rejected (wave_clear_mismatch)",
       not r["ok"] and "wave_clear_mismatch" in errors_reasons(r),
       repr(errors_reasons(r)[:3]))

    # 出口解锁早于最后一波清空
    early_exit = [
        started("waves", 0),
        wave_started(1, 0, 2, 1),
        exit_unlocked(2, 0),
        wave_cleared(3, 0),
        wave_started(4, 1, 2, 2),
        wave_cleared(5, 1),
        event(6, "level_victory", reason="exit_reached_after_unlock"),
    ]
    r = trace_replay.replay_document(waves_document(early_exit))
    ok("R49: exit_unlocked before the final wave clear is rejected"
       " (exit_unlocked_before_final_clear)",
       not r["ok"] and "exit_unlocked_before_final_clear" in errors_reasons(r),
       repr(errors_reasons(r)[:3]))

    # 重复出口解锁
    dup_exit = [
        started("waves", 0),
        wave_started(1, 0, 1, 1),
        wave_cleared(2, 0),
        exit_unlocked(3, 0),
        exit_unlocked(4, 0),
        event(5, "level_victory", reason="exit_reached_after_unlock"),
    ]
    r = trace_replay.replay_document(waves_document(dup_exit))
    ok("R50: a duplicate exit_unlocked is rejected",
       not r["ok"] and "duplicate_exit_unlock" in errors_reasons(r),
       repr(errors_reasons(r)[:3]))

    # waves 胜利前未清完全部波次
    early_victory = [
        started("waves", 0),
        wave_started(1, 0, 2, 1),
        wave_cleared(2, 0),
        event(3, "level_victory", reason="exit_reached_after_unlock"),
    ]
    r = trace_replay.replay_document(waves_document(early_victory))
    ok("R51: waves victory before all waves cleared is rejected",
       not r["ok"] and "victory_before_all_waves_cleared" in errors_reasons(r),
       repr(errors_reasons(r)[:3]))

    # holdout 提前胜利（无波次事件 → 不适用波次规则，但事件流本身合法 → ok）
    holdout_ok = [
        started("holdout", 0),
        event(1, "level_victory", reason="survive_duration"),
    ]
    r = trace_replay.replay_document(waves_document(holdout_ok))
    ok("R52: a holdout started→victory trace stays replayable (no invented rules)",
       r["ok"] and r["final_state"] == "victory", repr(r["errors"][:2]))

    # boss 模式里出现波次事件 → 拒绝
    boss_wave = [
        started("boss", 0),
        wave_started(1, 0, 1, 1),
    ]
    r = trace_replay.replay_document(waves_document(boss_wave))
    ok("R53: wave events outside waves mode are rejected",
       not r["ok"] and "wave_event_outside_waves_mode" in errors_reasons(r),
       repr(errors_reasons(r)[:3]))

    # 波次事件携带阶段身份 → 拒绝（waves 无阶段身份）
    staged_wave = [
        started("waves", 0),
        event(1, "wave_started", reason="wave_begin", stage_id="wave_0",
              stage_index=0, data={"wave": 0, "total": 1, "enemies": 1}),
    ]
    r = trace_replay.replay_document(waves_document(staged_wave))
    ok("R54: wave events carrying stage identity are rejected (invalid_wave_event)",
       not r["ok"] and "invalid_wave_event" in errors_reasons(r),
       repr(errors_reasons(r)[:3]))

    # data.total 不一致
    total_flip = [
        started("waves", 0),
        wave_started(1, 0, 2, 1),
        wave_cleared(2, 0),
        wave_started(3, 1, 3, 2),
        wave_cleared(4, 1),
        event(5, "level_victory", reason="all_waves_cleared"),
    ]
    r = trace_replay.replay_document(waves_document(total_flip))
    ok("R55: a contradictory data.total is rejected (wave_total_mismatch)",
       not r["ok"] and "wave_total_mismatch" in errors_reasons(r),
       repr(errors_reasons(r)[:3]))

    # 终结之后出现波次事件 → 既有 event_after_terminal 规则继续生效
    after_terminal = [
        started("waves", 0),
        wave_started(1, 0, 1, 1),
        wave_cleared(2, 0),
        event(3, "level_victory", reason="all_waves_cleared"),
        wave_started(4, 0, 1, 1),
    ]
    r = trace_replay.replay_document(waves_document(after_terminal))
    ok("R56: wave events after the terminal are rejected (event_after_terminal)",
       not r["ok"] and "event_after_terminal" in errors_reasons(r),
       repr(errors_reasons(r)[:3]))

    # 无波次事件的旧 waves trace（Phase 1.24 基线形态）在 v1 加性扩展下仍可回放
    legacy = [
        started("waves", 0),
        event(1, "level_victory", reason="exit_reached_after_unlock"),
    ]
    r = trace_replay.replay_document(waves_document(legacy))
    ok("R57: legacy waves traces without wave events remain replayable"
       " (v1 additive compatibility)", r["ok"], repr(r["errors"][:2]))

    # ==================== Phase 1.26：退出解锁是胜利的前置条件 ====================
    print()
    print("--- R58+. exit unlock is a precondition of waves victory (Phase 1.26) ---")

    # 全部波次已清空、但没有 exit_unlocked，却声称 exit_reached_after_unlock → 拒绝
    no_unlock = [
        started("waves", 0),
        wave_started(1, 0, 2, 1),
        wave_cleared(2, 0),
        wave_started(3, 1, 2, 2),
        wave_cleared(4, 1),
        event(5, "level_victory", reason="exit_reached_after_unlock"),
    ]
    r = trace_replay.replay_document(waves_document(no_unlock))
    ok("R58: a waves victory by exit_reached_after_unlock without exit_unlocked"
       " is rejected (victory_without_exit_unlock)",
       not r["ok"] and "victory_without_exit_unlock" in errors_reasons(r)
       and r["final_state"] != "victory",
       repr(errors_reasons(r)[:3]))

    # 出口解锁后才胜利是唯一合法顺序：victory 之后再来 exit_unlocked → 事件在终结之后
    unlock_after_victory = [
        started("waves", 0),
        wave_started(1, 0, 1, 1),
        wave_cleared(2, 0),
        event(3, "level_victory", reason="all_waves_cleared"),
        exit_unlocked(4, 0),
    ]
    r = trace_replay.replay_document(waves_document(unlock_after_victory))
    ok("R59: an exit_unlocked after the terminal victory is rejected"
       " (event_after_terminal)",
       not r["ok"] and "event_after_terminal" in errors_reasons(r),
       repr(errors_reasons(r)[:3]))

    # 向后兼容：无波次事件的旧 waves trace（Phase 1.24 形态）不被事后套用新规则
    legacy_exit_reason = [
        started("waves", 0),
        event(1, "level_victory", reason="exit_reached_after_unlock"),
    ]
    r = trace_replay.replay_document(waves_document(legacy_exit_reason))
    ok("R60: the new unlock rule does not retro-apply to old traces without"
       " wave events (compatibility guard)", r["ok"] and r["final_state"] == "victory",
       repr(r["errors"][:2]))

    # 删除**最后一个** wave_cleared（保留前面的波次）→ 最后波次未清空就宣称胜利
    dropped_last_clear = [
        started("waves", 0),
        wave_started(1, 0, 2, 1),
        wave_cleared(2, 0),
        wave_started(3, 1, 2, 2),
        event(4, "level_victory", reason="exit_reached_after_unlock"),
    ]
    r = trace_replay.replay_document(waves_document(dropped_last_clear))
    ok("R61: dropping only the final wave_cleared is rejected"
       " (victory_before_all_waves_cleared)",
       not r["ok"] and "victory_before_all_waves_cleared" in errors_reasons(r)
       and r["final_state"] != "victory",
       repr(errors_reasons(r)[:3]))

    # ==================== Phase 1.27：holdout 生成调度激活事件 ====================
    print()
    print("--- R62+. holdout spawn schedule events (Phase 1.27) ---")

    def spawn_started(sequence, index=0, entity="enemy", interval=0.3, max_alive=0,
                      **extra):
        return event(sequence, "spawn_schedule_started", reason="spawn_due",
                     data={"schedule": index, "entity": entity,
                           "interval": interval, "max_alive": max_alive}, **extra)

    legal_holdout = [
        started("holdout", 0),
        spawn_started(1),
        event(2, "level_victory", reason="survive_duration"),
    ]
    r = trace_replay.replay_document(document(legal_holdout))
    ok("R62: a legal holdout chain (started → schedule 0 → victory) replays"
       " and reports the activated schedule",
       r["ok"] and r["final_state"] == "victory"
       and r["spawn_schedules_started"] == [0], repr(r["errors"][:3]))

    duplicate_schedule = [
        started("holdout", 0),
        spawn_started(1),
        spawn_started(2),
        event(3, "level_victory", reason="survive_duration"),
    ]
    r = trace_replay.replay_document(document(duplicate_schedule))
    ok("R63: the same spawn schedule activating twice is rejected"
       " (duplicate_spawn_schedule)",
       not r["ok"] and "duplicate_spawn_schedule" in errors_reasons(r),
       repr(errors_reasons(r)[:3]))

    schedule_in_waves = [
        started("waves", 0),
        spawn_started(1),
    ]
    r = trace_replay.replay_document(document(schedule_in_waves))
    ok("R64: spawn schedule events outside holdout mode are rejected"
       " (spawn_event_outside_holdout_mode)",
       not r["ok"] and "spawn_event_outside_holdout_mode" in errors_reasons(r),
       repr(errors_reasons(r)[:3]))

    bad_payloads = [
        {"schedule": "0", "entity": "enemy", "interval": 0.3, "max_alive": 0},
        {"schedule": -1, "entity": "enemy", "interval": 0.3, "max_alive": 0},
        {"schedule": 0, "entity": 7, "interval": 0.3, "max_alive": 0},
        {"schedule": 0, "entity": "enemy", "interval": 0.0, "max_alive": 0},
        {"schedule": 0, "entity": "enemy", "interval": 0.3, "max_alive": -1},
        {"schedule": 0, "entity": "enemy", "interval": 0.3},
    ]
    bad_results = []
    for index, payload in enumerate(bad_payloads):
        doc = document([started("holdout", 0),
                        event(1, "spawn_schedule_started", reason="spawn_due",
                              data=payload)])
        bad_results.append(trace_replay.replay_document(doc))
    ok("R65: malformed spawn payloads are rejected (invalid_spawn_event)",
       all(not result["ok"] and "invalid_spawn_event" in errors_reasons(result)
           for result in bad_results),
       repr([errors_reasons(result)[:2] for result in bad_results]))

    staged_spawn = [
        started("holdout", 0),
        event(1, "spawn_schedule_started", reason="spawn_due",
              stage_id="stage_1", stage_index=0,
              data={"schedule": 0, "entity": "enemy", "interval": 0.3,
                    "max_alive": 0}),
    ]
    r = trace_replay.replay_document(document(staged_spawn))
    ok("R66: a spawn event carrying stage identity is rejected (invalid_spawn_event)",
       not r["ok"] and "invalid_spawn_event" in errors_reasons(r),
       repr(errors_reasons(r)[:3]))

    legacy_holdout = [
        started("holdout", 0),
        event(1, "level_victory", reason="survive_duration"),
    ]
    r = trace_replay.replay_document(document(legacy_holdout))
    ok("R67: legacy holdout traces without spawn events remain replayable"
       " (v1 additive compatibility)",
       r["ok"] and r["final_state"] == "victory"
       and r["spawn_schedules_started"] == [], repr(r["errors"][:2]))

    # ==================== Phase 1.28：跨模式语义一致性 ====================
    print()
    print("--- R68+. cross-mode semantic consistency (Phase 1.28) ---")

    # 阶段事件（LevelConfig 只允许 boss 声明 stages）出现在 waves trace → 拒绝
    stage_in_waves = [
        started("waves", 0),
        stage_started(1, 0, "clear_1"),
        stage_completed(2, 0, "clear_1"),
        event(3, "level_victory", reason="all_waves_cleared"),
    ]
    r = trace_replay.replay_document(document(stage_in_waves))
    ok("R68: stage events are boss-only and rejected inside a waves trace"
       " (stage_event_outside_boss_stages)",
       not r["ok"] and errors_reasons(r).count("stage_event_outside_boss_stages") == 2,
       repr(errors_reasons(r)[:3]))

    # 同样的阶段链出现在 holdout trace → 拒绝
    stage_in_holdout = [
        started("holdout", 0),
        stage_started(1, 0, "clear_1"),
        stage_completed(2, 0, "clear_1"),
        event(3, "level_victory", reason="survive_duration"),
    ]
    r = trace_replay.replay_document(document(stage_in_holdout))
    ok("R69: stage events are rejected inside a holdout trace (no declared stages)",
       not r["ok"] and "stage_event_outside_boss_stages" in errors_reasons(r),
       repr(errors_reasons(r)[:3]))

    # boss 模式但未声明阶段拓扑（stage_count = 0，即真实单阶段 Boss）→ 阶段链不可达
    staged_single_boss = [
        started("boss", 0),
        stage_started(1, 0, "clear_1"),
        stage_completed(2, 0, "clear_1"),
        boss_death_confirmed(3),
        event(4, "level_victory", reason="boss_defeated"),
    ]
    r = trace_replay.replay_document(document(staged_single_boss))
    ok("R70: a boss trace without a declared stage chain cannot carry stage events"
       " (single-stage boss emits none)",
       not r["ok"] and "stage_event_outside_boss_stages" in errors_reasons(r),
       repr(errors_reasons(r)[:3]))

    # 阶段索引超出声明的阶段数 → 拒绝（阶段身份必须落在声明的拓扑内）
    over_declared = [
        started("boss", 2),
        stage_started(1, 0, "clear_1"),
        stage_completed(2, 0, "clear_1"),
        stage_started(3, 2, "third_stage", "defeat_boss"),
    ]
    r = trace_replay.replay_document(document(over_declared))
    ok("R71: a stage index beyond data.stage_count is rejected"
       " (stage_start_outside_declared_count)",
       not r["ok"] and "stage_start_outside_declared_count" in errors_reasons(r),
       repr(errors_reasons(r)[:3]))

    # 终结原因必须属于该模式的可达集合（生产写入点见 LevelOrchestrator）
    impossible_victories = [("holdout", "boss_defeated"), ("waves", "survive_duration"),
                            ("boss", "survive_duration")]
    victory_results = []
    for mode, reason in impossible_victories:
        victory_results.append(
            (mode, reason, trace_replay.replay_document(document(
                [started(mode, 0), event(1, "level_victory", reason=reason)]))))
    ok("R72: terminal victory reasons outside the mode's reachable set are rejected"
       " (victory_reason_outside_mode)",
       all(not result["ok"] and "victory_reason_outside_mode" in errors_reasons(result)
           for _mode, _reason, result in victory_results),
       repr([(mode, reason, errors_reasons(result)[:1])
             for mode, reason, result in victory_results]))

    impossible_failures = [("holdout", "wave_timeout"), ("boss", "wave_timeout")]
    failure_results = [
        (mode, reason, trace_replay.replay_document(document(
            [started(mode, 0), event(1, "level_failed", reason=reason)])))
        for mode, reason in impossible_failures]
    legal_wave_timeout = trace_replay.replay_document(document(
        [started("waves", 0), event(1, "level_failed", reason="wave_timeout")]))
    ok("R73: terminal failure reasons outside the mode's reachable set are rejected"
       " (failure_reason_outside_mode) while the waves wave_timeout path stays legal",
       all(not result["ok"] and "failure_reason_outside_mode" in errors_reasons(result)
           for _mode, _reason, result in failure_results)
       and legal_wave_timeout["ok"] and legal_wave_timeout["failed"],
       repr([(mode, reason, errors_reasons(result)[:1])
             for mode, reason, result in failure_results]))

    # 模式必须显式声明：缺失 / 非法值都不能关闭模式专属规则
    bad_modes = [("missing", {"level_id": "probe"}), ("empty", {"mode": ""}),
                 ("unknown", {"mode": "survival"}), ("non-string", {"mode": 123})]
    bad_mode_results = []
    for label, payload in bad_modes:
        doc = document([event(0, "orchestration_started", reason="start", source="level_host",
                              data=payload),
                        event(1, "level_victory", reason="boss_defeated")])
        bad_mode_results.append((label, trace_replay.replay_document(doc)))
    ok("R74: orchestration_started.data.mode must declare boss/waves/holdout"
       " (invalid_start_mode)",
       all(not result["ok"] and "invalid_start_mode" in errors_reasons(result)
           for _label, result in bad_mode_results),
       repr([(label, errors_reasons(result)[:1]) for label, result in bad_mode_results]))

    # 逃逸口回归守卫：未声明模式的 trace 曾经可同时装下三种模式的特有事件
    mode_escape = [
        event(0, "orchestration_started", reason="start", source="level_host",
              data={"level_id": "probe", "stage_count": 0}),
        boss_death_confirmed(1),
        wave_started(2, 0, 1, 1),
        wave_cleared(3, 0),
        exit_unlocked(4, 0),
        spawn_started(5),
        stage_started(6, 0, "clear_1"),
        stage_completed(7, 0, "clear_1"),
        event(8, "level_victory", reason="boss_defeated"),
    ]
    r = trace_replay.replay_document(document(mode_escape))
    ok("R75: a trace without a declared mode cannot mix boss, waves and holdout"
       " exclusive events",
       not r["ok"] and "invalid_start_mode" in errors_reasons(r)
       and r["final_state"] != "victory", repr(errors_reasons(r)[:3]))

    # 合法模式专属链不得被公共规则误拒（三种模式各自合法，且不要求对方的事件）
    legal_boss_chain = [
        started("boss", 0),
        boss_death_confirmed(1),
        event(2, "level_victory", reason="boss_defeated"),
        event(3, "duplicate_event_ignored", reason="boss_death"),
    ]
    legal_waves_chain = [
        started("waves", 0),
        wave_started(1, 0, 1, 1),
        wave_cleared(2, 0),
        exit_unlocked(3, 0),
        event(4, "level_victory", reason="exit_reached_after_unlock"),
    ]
    legal_holdout_chain = [
        started("holdout", 0),
        spawn_started(1),
        event(2, "level_victory", reason="survive_duration"),
    ]
    chain_results = [(mode, trace_replay.replay_document(document(chain))) for mode, chain
                     in (("boss", legal_boss_chain), ("waves", legal_waves_chain),
                         ("holdout", legal_holdout_chain))]
    ok("R76: every mode's own legal chain still replays (no forced identical sequence:"
       " boss has no waves, waves has no stages, holdout has no boss death)",
       all(result["ok"] and result["final_state"] == "victory"
           for _mode, result in chain_results),
       repr([(mode, errors_reasons(result)[:2]) for mode, result in chain_results]))

    # 新模式门不得放宽既有前置约束
    no_boss_death = [started("boss", 0), event(1, "level_victory", reason="boss_defeated")]
    no_exit_unlock = [started("waves", 0), wave_started(1, 0, 1, 1), wave_cleared(2, 0),
                      event(3, "level_victory", reason="exit_reached_after_unlock")]
    ok("R77: missing terminal preconditions are still reported after the new mode gates"
       " (victory_without_boss_death / victory_without_exit_unlock)",
       "victory_without_boss_death" in errors_reasons(
           trace_replay.replay_document(document(no_boss_death)))
       and "victory_without_exit_unlock" in errors_reasons(
           trace_replay.replay_document(document(no_exit_unlock))),
       repr([errors_reasons(trace_replay.replay_document(document(no_boss_death)))[:2],
             errors_reasons(trace_replay.replay_document(document(no_exit_unlock)))[:2]]))

    # 终结之后仍只允许 duplicate_event_ignored，重复终结仍被拒
    after_terminal_stage = list(legal_boss_chain) + [stage_started(4, 0, "clear_1")]
    duplicate_terminal_stage = list(legal_boss_chain) + [
        event(4, "level_victory", reason="boss_defeated")]
    ok("R78: events after the terminal and repeated terminals stay rejected"
       " (event_after_terminal / duplicate_terminal)",
       "event_after_terminal" in errors_reasons(
           trace_replay.replay_document(document(after_terminal_stage)))
       and "duplicate_terminal" in errors_reasons(
           trace_replay.replay_document(document(duplicate_terminal_stage))),
       repr([errors_reasons(trace_replay.replay_document(document(after_terminal_stage)))[:2],
             errors_reasons(trace_replay.replay_document(document(duplicate_terminal_stage)))[:2]]))

    # 四条真实捕获事件链仍全部可回放（新规则不得误伤生产事件流）
    real_chains = []
    baseline_root = _TOOLS / "validator" / "baselines"
    for scenario in ("multi_stage_boss", "single_stage_boss", "waves", "holdout"):
        path = baseline_root / (scenario + ".json")
        baseline_document = json.loads(path.read_text(encoding="utf-8"))
        real_chains.append((scenario, trace_replay.replay(baseline_document["events"])))
    ok("R79: all four real captured event chains still replay under the cross-mode rules",
       all(result["ok"] for _scenario, result in real_chains),
       repr([(scenario, errors_reasons(result)[:2]) for scenario, result in real_chains]))

    # waves 专属事件出现在 holdout trace → 拒绝（R53 覆盖 boss，此处补上 holdout）
    waves_in_holdout = [started("holdout", 0), wave_started(1, 0, 1, 1),
                        event(2, "level_victory", reason="survive_duration")]
    r = trace_replay.replay_document(document(waves_in_holdout))
    ok("R80: waves-only events are rejected inside a holdout trace"
       " (wave_event_outside_waves_mode)",
       not r["ok"] and "wave_event_outside_waves_mode" in errors_reasons(r),
       repr(errors_reasons(r)[:3]))

    if _failures:
        print("FAILED: %d" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: orchestration trace replay unit tests")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(run())
