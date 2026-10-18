#!/usr/bin/env python3
"""Golden trace baseline unit tests（Phase 1.23）。

基线文件是**真实 Godot 运行**批准产物（`.ai/tools/validator/baselines/`）；本文件用它们
的事件构造比较输入，覆盖比较器的正常行为、必须失败的回归、输入异常与批准流程。

真实链路（沙箱生成 + 真实 Godot 探针 + 逐事件比较 + 注入差异）由独立 E2E 的 T 段与
`.ai/tools/validator/tests/` 之外的 `approve_trace_baselines.py` 覆盖；本文件不伪造
「真实 E2E 已通过」的结论。

用法: python .ai/tools/validator/tests/test_trace_baselines.py
退出码: 0 = 全部通过；1 = 有失败。
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

_TOOLS = Path(__file__).resolve().parents[2]              # .ai/tools
sys.path.insert(0, str(_TOOLS / "validator"))
sys.path.insert(0, str(_TOOLS / "e2e"))

import trace_baselines as tb                               # noqa: E402
import approve_trace_baselines as approve                  # noqa: E402

_failures: list[str] = []
SCENARIOS = ("multi_stage_boss", "single_stage_boss")


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + ((" | " + detail) if detail else ""))


def load_baseline(scenario: str) -> dict:
    return tb.load_baseline(tb.baseline_path_for(scenario))


def real_trace(baseline: dict, run_id: str = "run-unit", tail_shift: int = 0) -> dict:
    """用已批准基线的真实事件构造本次「运行」trace（只改运行标识 / 可选时间偏移）。"""
    events = copy.deepcopy(baseline["events"])
    for index, event in enumerate(events):
        event["run_id"] = run_id
        event["timestamp_ms"] = int(event.get("timestamp_ms", 0)) + tail_shift * index
    return {
        "document": tb.TRACE_DOCUMENT,
        "schema_version": tb.TRACE_SCHEMA_VERSION,
        "run_id": run_id,
        "config_path": "res://Levels/unit_baseline.json",
        "event_count": len(events),
        "dropped_events": 0,
        "events": events,
    }


def resequence(events: list) -> list:
    for index, event in enumerate(events):
        event["sequence"] = index
    return events


def compare(baseline: dict, trace: dict) -> dict:
    return tb.compare(baseline, trace, baseline_path="<unit>")


def write_json(path: Path, document) -> Path:
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")
    return path


def expect_status(label: str, result: dict, status: str, exit_code: int,
                  category: str = "", path_suffix: str = "") -> None:
    differences = result.get("differences") or []
    matched_category = any(difference.get("category") == category
                           and (not path_suffix
                                or str(difference.get("field_path") or "").endswith(path_suffix))
                           for difference in differences)
    ok(label, result["status"] == status and result.get("exit_code") == exit_code
       and (not category or matched_category),
       repr({"status": result["status"], "exit": result.get("exit_code"),
             "summary": result.get("summary"),
             "categories": [difference.get("category") for difference in differences[:4]]}))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    baselines = {scenario: load_baseline(scenario) for scenario in SCENARIOS}
    multi = baselines["multi_stage_boss"]
    single = baselines["single_stage_boss"]
    real_multi = real_trace(multi)
    real_single = real_trace(single)

    # ==================== U1. 比较器正常行为 ====================
    print("--- U1. comparator happy paths ---")
    result = compare(multi, real_multi)
    ok("U1: a real multi-stage trace identical to its baseline is PASS",
       result["status"] == "PASS" and result["exit_code"] == 0
       and result["matched_event_count"] == result["expected_event_count"]
       == result["actual_event_count"] == len(multi["events"])
       and not result["differences"], result["summary"])
    required_keys = ("status", "scenario_id", "baseline_version",
                     "actual_trace_schema_version", "expected_event_count",
                     "actual_event_count", "matched_event_count", "differences",
                     "first_difference", "summary")
    ok("U2: the result carries every documented comparison field",
       all(key in result for key in required_keys), repr(sorted(result)))
    ok("U3: the comparison result reports the approved baseline identity",
       result["scenario_id"] == "multi_stage_boss"
       and result["baseline_version"] == multi["baseline_version"]
       and result["actual_trace_schema_version"] == tb.TRACE_SCHEMA_VERSION
       and result["approved_behavior_version"] == multi["approved_behavior_version"], "")
    ok("U4: a different run_id still passes (explicit dynamic-field policy)",
       compare(single, real_trace(single, run_id="run-other-42"))["status"] == "PASS")
    ok("U5: different timestamps with the same order still pass",
       compare(single, real_trace(single, tail_shift=97))["status"] == "PASS")
    ignored_policy = copy.deepcopy(single)
    ignored_policy["comparison_policy"]["data"] = {
        "mode": "strict_with_ignored_keys",
        "ignored_fields": ["boss_defeated_events"],
        "numeric_tolerance": 0.0,
    }
    data_changed = copy.deepcopy(real_single)
    data_changed["events"][1]["data"]["boss_defeated_events"] = 9
    ok("U6: a data key declared dynamic by policy is ignored (and only that key)",
       compare(ignored_policy, data_changed)["status"] == "PASS",
       compare(ignored_policy, data_changed)["summary"])
    strict_result = compare(single, data_changed)
    expect_status("U7: the same data change is a REGRESSION under the strict default policy",
                  strict_result, tb.STATUS_REGRESSION, 1, "DATA_FIELD_CHANGED",
                  "data.boss_defeated_events")
    ok("U8: strict comparison of event_type / stage identity cannot be disabled by policy",
       bool(tb.validate_policy({"version": 1,
                                "ignored_event_fields": ["event_type"]})))

    # ==================== U2. 必须失败的回归 ====================
    print("--- U2. regressions that must fail ---")
    deleted = copy.deepcopy(real_multi)
    deleted["events"] = resequence([event for event in deleted["events"]
                                    if not (event["event_type"] == "stage_started"
                                            and event["stage_index"] == 1)])
    deleted["event_count"] = len(deleted["events"])
    expect_status("U9: deleting a stage_started event can never pass",
                  compare(multi, deleted), tb.STATUS_INVALID_TRACE, 1, "TRACE_INVALID")

    dropped = copy.deepcopy(real_multi)
    dropped["events"] = resequence(dropped["events"][:-1])
    dropped["event_count"] = len(dropped["events"])
    expect_status("U10: deleting the last event is an EVENT_MISSING regression",
                  compare(multi, dropped), tb.STATUS_REGRESSION, 1, "EVENT_MISSING")

    extra = copy.deepcopy(real_multi)
    extra_event = copy.deepcopy(extra["events"][-1])
    extra_event["sequence"] = len(extra["events"])
    extra_event["timestamp_ms"] = extra["events"][-1]["timestamp_ms"] + 1
    extra["events"].append(extra_event)
    extra["event_count"] = len(extra["events"])
    expect_status("U11: an unapproved extra event is an EVENT_EXTRA regression",
                  compare(multi, extra), tb.STATUS_REGRESSION, 1, "EVENT_EXTRA")

    reason = copy.deepcopy(real_multi)
    for event in reason["events"]:
        if event["event_type"] == "level_victory":
            event["reason"] = "forced"
    expect_status("U12: changing the victory reason is a REASON_CHANGED regression",
                  compare(multi, reason), tb.STATUS_REGRESSION, 1, "REASON_CHANGED", ".reason")

    identity = copy.deepcopy(real_multi)
    for event in identity["events"]:
        if event["event_type"] == "boss_death_confirmed":
            event["instance_name"] = "WrongBoss"
    expect_status("U13: changing the boss instance identity is an IDENTITY_CHANGED regression",
                  compare(multi, identity), tb.STATUS_REGRESSION, 1, "IDENTITY_CHANGED",
                  "instance_name")

    stage_id = copy.deepcopy(real_multi)
    for event in stage_id["events"]:
        if event.get("stage_id") == "clear_1":
            event["stage_id"] = "clear_renamed"
    expect_status("U14: changing a stage id can never pass",
                  compare(multi, stage_id), tb.STATUS_INVALID_TRACE, 1)

    stage_index = copy.deepcopy(real_multi)
    for event in stage_index["events"]:
        if event.get("stage_id") == "boss":
            event["stage_index"] = 0
    expect_status("U15: changing a stage index can never pass",
                  compare(multi, stage_index), tb.STATUS_INVALID_TRACE, 1)

    no_boss_death = copy.deepcopy(real_multi)
    no_boss_death["events"] = resequence([event for event in no_boss_death["events"]
                                          if event["event_type"] != "boss_death_confirmed"])
    no_boss_death["event_count"] = len(no_boss_death["events"])
    expect_status("U16: removing boss_death_confirmed can never pass",
                  compare(multi, no_boss_death), tb.STATUS_INVALID_TRACE, 1)

    duplicate_death = copy.deepcopy(real_multi)
    for event in duplicate_death["events"]:
        if event["event_type"] == "boss_death_confirmed":
            clone = copy.deepcopy(event)
            duplicate_death["events"].insert(event["sequence"], clone)
            break
    resequence(duplicate_death["events"])
    duplicate_death["event_count"] = len(duplicate_death["events"])
    expect_status("U17: a duplicated boss_death_confirmed can never pass",
                  compare(multi, duplicate_death), tb.STATUS_INVALID_TRACE, 1)

    failed = copy.deepcopy(real_multi)
    for event in failed["events"]:
        if event["event_type"] == "level_victory":
            event["event_type"] = "level_failed"
            event["reason"] = "player_died"
    failed_result = compare(multi, failed)
    ok("U18: turning victory into failure is never PASS and reports the terminal change",
       failed_result["status"] != "PASS" and failed_result["exit_code"] != 0
       and any(difference["category"] in ("EVENT_TYPE_CHANGED", "TERMINAL_EVENT_CHANGED",
                                          "FINAL_STATE_CHANGED", "TRACE_INVALID")
               for difference in failed_result["differences"]),
       failed_result["summary"])

    duplicate_terminal = copy.deepcopy(real_multi)
    terminal = copy.deepcopy([event for event in duplicate_terminal["events"]
                              if event["event_type"] in ("level_victory", "level_failed")][0])
    terminal["sequence"] = len(duplicate_terminal["events"])
    terminal["timestamp_ms"] = duplicate_terminal["events"][-1]["timestamp_ms"] + 1
    duplicate_terminal["events"].append(terminal)
    duplicate_terminal["event_count"] = len(duplicate_terminal["events"])
    expect_status("U19: a duplicated terminal event can never pass",
                  compare(multi, duplicate_terminal), tb.STATUS_INVALID_TRACE, 1)

    after_terminal = copy.deepcopy(real_multi)
    late_event = copy.deepcopy(after_terminal["events"][1])
    late_event["sequence"] = len(after_terminal["events"])
    late_event["timestamp_ms"] = after_terminal["events"][-1]["timestamp_ms"] + 1
    after_terminal["events"].append(late_event)
    after_terminal["event_count"] = len(after_terminal["events"])
    expect_status("U20: an event after the terminal event can never pass",
                  compare(multi, after_terminal), tb.STATUS_INVALID_TRACE, 1)

    transition = copy.deepcopy(real_multi)
    inserted = copy.deepcopy([event for event in transition["events"]
                              if event["event_type"] == "stage_transitioned"][-1])
    inserted["sequence"] = 2
    inserted["timestamp_ms"] = transition["events"][2]["timestamp_ms"]
    transition["events"].insert(2, inserted)
    resequence(transition["events"])
    transition["event_count"] = len(transition["events"])
    expect_status("U21: an unapproved stage transition can never pass",
                  compare(multi, transition), tb.STATUS_INVALID_TRACE, 1)

    swapped = copy.deepcopy(real_multi)
    swap_baseline = copy.deepcopy(multi)
    duplicates = [event for event in swapped["events"]
                  if event["event_type"] == "duplicate_event_ignored"]
    if len(duplicates) >= 2:
        duplicates[0]["reason"], duplicates[1]["reason"] = "boss_death", "player_death"
        duplicates[1]["reason"], duplicates[0]["reason"] = "player_death", "boss_death"
        for event in swap_baseline["events"]:
            if event["event_type"] == "duplicate_event_ignored":
                event["reason"] = "boss_death"
        swap_result = compare(swap_baseline, swapped)
        ok("U22: swapping two event positions is never PASS",
           swap_result["status"] != "PASS" and swap_result["exit_code"] != 0,
           swap_result["summary"])
    else:                                                    # pragma: no cover - 防御
        ok("U22: swapping two event positions is never PASS", False,
           "baseline holds fewer than two duplicate events")

    early_boss = copy.deepcopy(real_multi)
    early_boss["events"] = resequence(
        [early_boss["events"][0]] + [event for event in early_boss["events"]
                                     if event["event_type"] == "stage_started"
                                     and event["stage_index"] == 1]
        + [event for event in early_boss["events"][1:]
           if not (event["event_type"] == "stage_started" and event["stage_index"] == 1)])
    early_boss["event_count"] = len(early_boss["events"])
    expect_status("U23: moving the boss stage earlier can never pass",
                  compare(multi, early_boss), tb.STATUS_INVALID_TRACE, 1)

    # ==================== U3. 输入异常 ====================
    print("--- U3. invalid inputs ---")
    with tempfile.TemporaryDirectory(prefix="trace_baseline_unit_") as raw:
        work = Path(raw)
        trace_path = write_json(work / "real.json", real_multi)
        status_missing = tb.compare_files(trace_path, work / "absent.json",
                                          scenario_id="multi_stage_boss")
        ok("U24: a missing baseline is BASELINE_MISSING (exit 2), never PASS",
           status_missing["status"] == tb.STATUS_BASELINE_MISSING
           and status_missing["exit_code"] == 2, status_missing["summary"])

        broken = work / "broken.json"
        broken.write_text("{not json", encoding="utf-8", newline="\n")
        status_broken = tb.compare_files(trace_path, broken, scenario_id="multi_stage_boss")
        ok("U25: malformed baseline JSON is INVALID_BASELINE (exit 2)",
           status_broken["status"] == tb.STATUS_INVALID_BASELINE
           and status_broken["exit_code"] == 2, status_broken["summary"])

        bad_trace = work / "bad_trace.json"
        bad_trace.write_text("[]", encoding="utf-8", newline="\n")
        status_bad_trace = tb.compare_files(bad_trace, tb.baseline_path_for("multi_stage_boss"))
        ok("U26: a malformed trace is INVALID_TRACE (exit 1)",
           status_bad_trace["status"] == tb.STATUS_INVALID_TRACE
           and status_bad_trace["exit_code"] == 1, status_bad_trace["summary"])

        schema = copy.deepcopy(real_multi)
        schema["schema_version"] = 2
        expect_status("U27: an unknown trace schema version is INVALID_TRACE with a mismatch diff",
                      compare(multi, schema), tb.STATUS_INVALID_TRACE, 1,
                      "TRACE_SCHEMA_MISMATCH")

        incomplete = copy.deepcopy(real_multi)
        incomplete["dropped_events"] = 1
        expect_status("U28: an incomplete (dropped events) trace is INCOMPLETE (exit 1)",
                      compare(multi, incomplete), tb.STATUS_INCOMPLETE, 1, "TRACE_INCOMPLETE")

        truncated = copy.deepcopy(real_multi)
        truncated["event_count"] = len(truncated["events"]) + 3
        expect_status("U29: a truncated trace (event_count mismatch) is INCOMPLETE",
                      compare(multi, truncated), tb.STATUS_INCOMPLETE, 1)

        gaps = copy.deepcopy(real_multi)
        gaps["events"][1]["sequence"] = 0
        expect_status("U30: a duplicate / regressed sequence is INVALID_TRACE",
                      compare(multi, gaps), tb.STATUS_INVALID_TRACE, 1)

        backwards = copy.deepcopy(real_multi)
        backwards["events"][-1]["timestamp_ms"] = -3
        expect_status("U31: a negative / decreasing timestamp is INVALID_TRACE",
                      compare(multi, backwards), tb.STATUS_INVALID_TRACE, 1)

        replay_failure = copy.deepcopy(real_multi)
        victory = [event for event in replay_failure["events"]
                   if event["event_type"] == "level_victory"][0]
        replay_failure["events"].remove(victory)
        replay_failure["events"].insert(1, victory)
        resequence(replay_failure["events"])
        replay_failure["event_count"] = len(replay_failure["events"])
        expect_status("U32: a structurally valid but un-replayable order is INVALID_TRACE",
                      compare(multi, replay_failure), tb.STATUS_INVALID_TRACE, 1,
                      "TRACE_INVALID")

        no_version = copy.deepcopy(multi)
        no_version.pop("baseline_version", None)
        expect_status("U33: a baseline without baseline_version is INVALID_BASELINE",
                      compare(no_version, real_multi), tb.STATUS_INVALID_BASELINE, 2,
                      "BASELINE_INVALID")

        unknown_policy = copy.deepcopy(multi)
        unknown_policy["comparison_policy"]["ignore_everything"] = True
        expect_status("U34: an unknown comparison-policy field is INVALID_BASELINE",
                      compare(unknown_policy, real_multi), tb.STATUS_INVALID_BASELINE, 2)

        candidate_status = copy.deepcopy(multi)
        candidate_status["approval"] = {"status": "candidate", "approver": "x",
                                        "approved_at": "2026-10-17"}
        expect_status("U35: an unapproved (candidate) baseline is INVALID_BASELINE",
                      compare(candidate_status, real_multi), tb.STATUS_INVALID_BASELINE, 2)

        no_policy_events = copy.deepcopy(multi)
        no_policy_events["events"] = []
        expect_status("U36: a baseline with no approved events is INVALID_BASELINE",
                      compare(no_policy_events, real_multi), tb.STATUS_INVALID_BASELINE, 2)

    # ==================== U4. 批准流程 ====================
    print("--- U4. approval flow ---")
    ok("U37: the approved baselines record who approved them and why",
       all(isinstance(baseline["approval"].get("approver"), str)
           and baseline["approval"]["approver"].strip()
           and isinstance(baseline["approval"].get("note"), str)
           and baseline["approval"]["note"].strip()
           and baseline["approval"]["status"] == "approved"
           for baseline in baselines.values()),
       repr({scenario: baselines[scenario]["approval"]["status"]
             for scenario in SCENARIOS}))
    ok("U38: the baseline fingerprint ignores only run_id / timestamp_ms",
       approve.normalized_fingerprint(multi)
       == approve.normalized_fingerprint(real_trace(multi, run_id="run-x", tail_shift=5))
       and approve.normalized_fingerprint(multi)
       != approve.normalized_fingerprint({
           **multi,
           "events": [{**event, "reason": "forced"}
                      if event["event_type"] == "level_victory" else event
                      for event in multi["events"]],
       }), "")

    candidate = tb.build_baseline(
        real_multi, scenario_id="multi_stage_boss",
        scenario_description=multi["scenario_description"],
        approved_behavior_version=multi["approved_behavior_version"],
        approval={"status": "candidate", "candidate_generated_at": "2026-10-17T00:00:00",
                  "candidate_fingerprint": approve.normalized_fingerprint(multi)},
        source={"captured_by": "unit-test real-baseline replay"},
        coverage=multi["coverage"])
    ok("U39: a candidate built from the real approved events passes candidate validation",
       not approve._validate_candidate(candidate),
       repr(approve._validate_candidate(candidate)))

    forged = copy.deepcopy(candidate)
    forged["source"].pop("captured_by", None)
    ok("U40: a candidate without real-capture provenance is rejected",
       bool(approve._validate_candidate(forged)))
    forged_events = copy.deepcopy(candidate)
    forged_events["events"][1]["sequence"] = 0
    ok("U41: a candidate whose events break the trace contract is rejected",
       bool(approve._validate_candidate(forged_events)))

    with tempfile.TemporaryDirectory(prefix="trace_baseline_approve_") as raw:
        base_dir = Path(raw)
        candidate_dir = base_dir / "candidates"
        candidate_dir.mkdir()
        candidate_path = write_json(candidate_dir / "multi_stage_boss.candidate.json",
                                    candidate)
        target = base_dir / "multi_stage_boss.json"

        refused = approve.main(["apply", "--candidate", str(candidate_path),
                                "--baseline-dir", str(base_dir),
                                "--approver", "reviewer", "--note", "unit"])
        ok("U42: apply refuses to write without --i-approve (and writes nothing)",
           refused == 2 and not target.exists())

        invalid_candidate = copy.deepcopy(candidate)
        invalid_candidate["events"][2]["event_type"] = "level_victory"
        invalid_path = write_json(candidate_dir / "invalid.candidate.json",
                                  invalid_candidate)
        rejected = approve.main(["apply", "--candidate", str(invalid_path),
                                 "--baseline-dir", str(base_dir), "--approver", "reviewer",
                                 "--note", "unit", "--i-approve"])
        ok("U43: an invalid candidate cannot be approved (exit 1, no baseline written)",
           rejected == 1 and not target.exists(),
           "exit=%d exists=%s" % (rejected, target.exists()))

        applied = approve.main(["apply", "--candidate", str(candidate_path),
                                "--baseline-dir", str(base_dir), "--approver", "reviewer",
                                "--note", "unit approval", "--i-approve"])
        approved = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else {}
        ok("U44: an explicit apply writes an approved baseline v1 in the target directory",
           applied == 0 and approved.get("approval", {}).get("status") == "approved"
           and approved.get("approval", {}).get("approver") == "reviewer"
           and approved.get("baseline_version") == 1, repr(approved.get("approval")))
        ok("U45: the written baseline satisfies the baseline contract",
           not tb.validate_baseline(approved) if approved else False,
           repr(tb.validate_baseline(approved) if approved else ["missing"]))

        again = approve.main(["apply", "--candidate", str(candidate_path),
                              "--baseline-dir", str(base_dir), "--approver", "reviewer",
                              "--note", "second approval", "--i-approve"])
        bumped = json.loads(target.read_text(encoding="utf-8"))
        ok("U46: re-approving bumps baseline_version and keeps an approval record",
           again == 0 and bumped.get("baseline_version") == 2
           and bumped.get("approval", {}).get("previous_baseline_version") == 1,
           repr(bumped.get("approval")))
        review = approve.main(["review", "--candidate", str(candidate_path),
                               "--baseline-dir", str(base_dir)])
        ok("U47: review of a valid candidate succeeds (approval is not implied)",
           review == 0, "exit=%d" % review)

        # ---- Phase 1.24（任务 B）：review 后篡改候选，apply 必须拒绝 ----
        def _mtime():
            return (target.stat().st_mtime_ns, target.read_bytes()) \
                if target.exists() else (0, b"")

        before = _mtime()

        tampered_reason = copy.deepcopy(candidate)
        for event in tampered_reason["events"]:
            if event["event_type"] == "level_victory":
                event["reason"] = "forced"
        tampered_path = write_json(candidate_dir / "tampered_reason.candidate.json",
                                   tampered_reason)
        # 元数据指纹仍是原内容的：review 必须发现「内容 ≠ 指纹」并拒绝。
        review_tampered = approve.main(["review", "--candidate", str(tampered_path),
                                        "--baseline-dir", str(base_dir)])
        ok("U49: review rejects a candidate whose content no longer matches its"
           " recorded fingerprint", review_tampered == 1, "exit=%d" % review_tampered)
        applied_tampered = approve.main(["apply", "--candidate", str(tampered_path),
                                         "--baseline-dir", str(base_dir),
                                         "--approver", "reviewer", "--note", "unit",
                                         "--i-approve"])
        ok("U50: apply refuses a reason-tampered candidate (exit 1, baseline untouched)",
           applied_tampered == 1 and _mtime() == before,
           "exit=%d changed=%s" % (applied_tampered, _mtime() != before))

        tampered_stage = copy.deepcopy(candidate)
        for event in tampered_stage["events"]:
            if event["event_type"] == "stage_started":
                event["stage_id"] = "renamed_stage"
        tampered_stage["approval"]["candidate_fingerprint"] = \
            approve.normalized_fingerprint(tampered_stage)     # 指纹重算过：内容一致
        tampered_stage_path = write_json(
            candidate_dir / "tampered_stage.candidate.json", tampered_stage)
        # 指纹一致但内容是**新行为**：review/apply 能通过工具校验（它只验证一致性），
        # 但会以「与现有基线的差异」呈现 —— 审查者据此决定。这里断言它不会静默覆盖为
        # 同版本，而是 version+1 且差异可见（apply 前打印 diff）。
        applied_stage = approve.main(["apply", "--candidate", str(tampered_stage_path),
                                      "--baseline-dir", str(base_dir),
                                      "--approver", "reviewer", "--note", "unit",
                                      "--i-approve"])
        bumped_stage = json.loads(target.read_text(encoding="utf-8"))
        ok("U51: apply refuses a candidate whose renamed stage breaks the replay"
           " chain (exit 1, baseline untouched)",
           applied_stage == 1 and bumped_stage.get("baseline_version") == 2
           and not any(event.get("stage_id") == "renamed_stage"
                       for event in bumped_stage.get("events") or []),
           "exit=%d version=%s" % (applied_stage, bumped_stage.get("baseline_version")))

        # 恢复干净基线（v1 语义）供后续断言：重新 apply 原始候选。
        restore = approve.main(["apply", "--candidate", str(candidate_path),
                                "--baseline-dir", str(base_dir), "--approver", "reviewer",
                                "--note", "restore", "--i-approve"])
        before = _mtime()

        no_fingerprint = copy.deepcopy(candidate)
        no_fingerprint["approval"].pop("candidate_fingerprint", None)
        no_fp_path = write_json(candidate_dir / "no_fingerprint.candidate.json",
                                no_fingerprint)
        applied_no_fp = approve.main(["apply", "--candidate", str(no_fp_path),
                                      "--baseline-dir", str(base_dir),
                                      "--approver", "reviewer", "--note", "unit",
                                      "--i-approve"])
        ok("U52: apply refuses a candidate without a recorded fingerprint (exit 1,"
           " baseline untouched)",
           applied_no_fp == 1 and _mtime() == before, "exit=%d" % applied_no_fp)

        appended = copy.deepcopy(candidate)
        extra_event = copy.deepcopy(appended["events"][-1])
        extra_event["event_type"] = "duplicate_event_ignored"
        appended["events"].append(extra_event)
        appended["event_count"] = len(appended["events"])
        appended_path = write_json(candidate_dir / "appended.candidate.json",
                                   appended)
        applied_appended = approve.main(["apply", "--candidate", str(appended_path),
                                         "--baseline-dir", str(base_dir),
                                         "--approver", "reviewer", "--note", "unit",
                                         "--i-approve"])
        ok("U53: apply refuses a candidate with appended events (metadata fingerprint"
           " no longer matches content, exit 1, baseline untouched)",
           applied_appended == 1 and _mtime() == before, "exit=%d" % applied_appended)

        replaced = copy.deepcopy(candidate)
        replaced["scenario_id"] = "single_stage_boss"      # 换了场景身份的候选
        replaced["approval"]["candidate_fingerprint"] = \
            approve.normalized_fingerprint(replaced)
        replaced_path = write_json(candidate_dir / "replaced.candidate.json", replaced)
        applied_replaced = approve.main(["apply", "--candidate", str(replaced_path),
                                         "--baseline-dir", str(base_dir),
                                         "--approver", "reviewer", "--note", "unit",
                                         "--i-approve"])
        ok("U54: apply routes by the candidate's own scenario id (a replaced candidate"
           " targets its own baseline, never the reviewed one)",
           applied_replaced in (0, 1)
           and json.loads(target.read_text(encoding="utf-8")).get("scenario_id")
           == "multi_stage_boss", "exit=%d" % applied_replaced)
        ok("U55: apply leaves no temporary write artifacts next to the baseline",
           not list(base_dir.glob("*.tmp")),
           str(sorted(p.name for p in base_dir.glob("*.tmp"))))
        ok("U56: the explicit approvals in this section wrote only the temp baseline"
           " (the toolchain baselines are untouched)",
           all(load_baseline(scenario) == baselines[scenario] for scenario in SCENARIOS))

    # ---- Phase 1.25：waves 语义事件的比较器回归覆盖（合成合法 trace）----
    # 合成 trace 只用于**单元级**比较器断言；正式黄金基线仍只能来自真实捕获。
    def waves_events():
        return [
            {"schema_version": 1, "run_id": "run-unit", "sequence": 0,
             "event_type": "orchestration_started", "timestamp_ms": 0,
             "stage_id": None, "stage_index": None, "source": "orchestrator",
             "reason": "waves", "entity_id": None, "instance_name": None,
             "data": {"mode": "waves", "stage_count": 0}},
            {"schema_version": 1, "run_id": "run-unit", "sequence": 1,
             "event_type": "wave_started", "timestamp_ms": 5,
             "stage_id": None, "stage_index": None, "source": "orchestrator",
             "reason": "wave_begin", "entity_id": None, "instance_name": None,
             "data": {"wave": 0, "total": 2, "enemies": 1}},
            {"schema_version": 1, "run_id": "run-unit", "sequence": 2,
             "event_type": "wave_cleared", "timestamp_ms": 10,
             "stage_id": None, "stage_index": None, "source": "orchestrator",
             "reason": "wave_cleared", "entity_id": None, "instance_name": None,
             "data": {"wave": 0}},
            {"schema_version": 1, "run_id": "run-unit", "sequence": 3,
             "event_type": "wave_started", "timestamp_ms": 15,
             "stage_id": None, "stage_index": None, "source": "orchestrator",
             "reason": "wave_begin", "entity_id": None, "instance_name": None,
             "data": {"wave": 1, "total": 2, "enemies": 2}},
            {"schema_version": 1, "run_id": "run-unit", "sequence": 4,
             "event_type": "wave_cleared", "timestamp_ms": 20,
             "stage_id": None, "stage_index": None, "source": "orchestrator",
             "reason": "wave_cleared", "entity_id": None, "instance_name": None,
             "data": {"wave": 1}},
            {"schema_version": 1, "run_id": "run-unit", "sequence": 5,
             "event_type": "exit_unlocked", "timestamp_ms": 25,
             "stage_id": None, "stage_index": None, "source": "orchestrator",
             "reason": "all_waves_cleared", "entity_id": None, "instance_name": None,
             "data": {"wave": 1}},
            {"schema_version": 1, "run_id": "run-unit", "sequence": 6,
             "event_type": "level_victory", "timestamp_ms": 30,
             "stage_id": None, "stage_index": None, "source": "orchestrator",
             "reason": "exit_reached_after_unlock", "entity_id": None,
             "instance_name": None, "data": {}},
        ]

    def waves_trace_doc(events):
        return {"document": tb.TRACE_DOCUMENT, "schema_version": 1,
                "run_id": "run-unit", "config_path": "res://Levels/x.json",
                "event_count": len(events), "dropped_events": 0, "events": events}

    waves_baseline = tb.build_baseline(
        waves_trace_doc(waves_events()), scenario_id="unit_waves",
        scenario_description="unit-level waves semantics",
        approved_behavior_version="phase-1.25-wave-events",
        approval={"status": "approved", "approver": "unit-reviewer",
                  "approved_at": "2026-10-18",
                  "candidate_fingerprint": "unit"},
        source={"captured_by": "unit-test synthetic (never a real baseline)"},
        coverage=["waves 语义事件回归覆盖"])

    def waves_categories(mutate):
        events = mutate(copy.deepcopy(waves_events()))
        return [d["category"] for d in
                compare(waves_baseline, waves_trace_doc(events))["differences"]]

    # 分层语义（Phase 1.25）：回放非法的突变 → INVALID_TRACE（exit 1，由回放层
    # 给出精确定位）；回放合法但语义变化 → REGRESSION（比较器逐事件差异）。
    # 两种路径都以非零退出码失败——没有任何一种能伪装成 PASS。

    def resequenced(events):
        for index, event_item in enumerate(events):
            event_item["sequence"] = index
        return events

    ok("U57: the synthetic waves trace matches its baseline event by event"
       " (comparator accepts the new event types)",
       compare(waves_baseline, waves_trace_doc(waves_events()))["status"]
       == tb.STATUS_PASS, repr(compare(waves_baseline,
                                       waves_trace_doc(waves_events()))["differences"][:2]))

    missing_clear = resequenced([x for x in waves_events()
                                 if x["event_type"] != "wave_cleared"])
    r = compare(waves_baseline, waves_trace_doc(missing_clear))
    ok("U58: deleting a wave_cleared fails with non-zero semantics"
       " (TRACE_INVALID from the replay layer: next wave starts before clear)",
       r["status"] == tb.STATUS_INVALID_TRACE and r["exit_code"] == 1
       and any("was not cleared" in str(d.get("actual"))
               for d in r["differences"]),
       repr([(d["category"], str(d.get("actual"))[:60])
             for d in r["differences"][:2]]))

    swapped = resequenced([waves_events()[0], waves_events()[2], waves_events()[1]]
                          + waves_events()[3:])
    r = compare(waves_baseline, waves_trace_doc(swapped))
    ok("U59: swapping started/cleared of the same wave is rejected"
       " (TRACE_INVALID: cleared before started)", r["exit_code"] == 1
       and r["status"] == tb.STATUS_INVALID_TRACE,
       repr([(d["category"], str(d.get("actual"))[:60])
             for d in r["differences"][:2]]))

    cats = [d["category"] for d in
            compare(waves_baseline, waves_trace_doc(
                [{**x, "data": {**x["data"], "wave": 9}}
                 if x["event_type"] == "exit_unlocked" else x
                 for x in waves_events()]))["differences"]]
    ok("U60: mutating the exit_unlocked wave reference is DATA_FIELD_CHANGED"
       " (REGRESSION, exit 1)", "DATA_FIELD_CHANGED" in cats, repr(cats))

    missing_exit = resequenced([x for x in waves_events()
                                if x["event_type"] != "exit_unlocked"])
    r = compare(waves_baseline, waves_trace_doc(missing_exit))
    ok("U61: dropping the exit unlock is EVENT_MISSING (exit semantics protected"
       " by the event stream, not just the final result)",
       r["status"] == tb.STATUS_REGRESSION and r["exit_code"] == 1
       and any(d["category"] == "EVENT_MISSING"
               and "exit_unlocked" in str(d.get("expected"))
               for d in r["differences"]),
       repr([(d["category"], d.get("actual")) for d in r["differences"][:2]]))

    dup_terminal = resequenced(waves_events()
                               + [{**waves_events()[-1], "timestamp_ms": 35}])
    r = compare(waves_baseline, waves_trace_doc(dup_terminal))
    ok("U62: a duplicate level_victory fails (TRACE_INVALID from the replay layer:"
       " duplicate_terminal)", r["exit_code"] == 1
       and r["status"] == tb.STATUS_INVALID_TRACE
       and any("level_victory after level_victory" in str(d.get("actual"))
               for d in r["differences"]),
       repr([(d["category"], str(d.get("actual"))[:60])
             for d in r["differences"][:2]]))

    r = compare(waves_baseline, waves_trace_doc(
        [{**x, "data": {**x["data"], "total": 5}}
         if x["event_type"] == "wave_started" and x["data"].get("wave") == 0 else x
         for x in waves_events()]))
    ok("U63: changing the wave total fails (TRACE_INVALID from the replay layer:"
       " wave_total_mismatch)", r["exit_code"] == 1
       and r["status"] == tb.STATUS_INVALID_TRACE
       and any("wave_total_mismatch" in str(d)
               for d in r["differences"]),
       repr([(d["category"], str(d.get("actual"))[:70])
             for d in r["differences"][:2]]))

    ok("U48: the toolchain-approved baselines are untouched by this unit test",
       all(load_baseline(scenario) == baselines[scenario] for scenario in SCENARIOS))

    print()
    if _failures:
        for failure in _failures:
            print("FAIL: " + failure, file=sys.stderr)
        print("FAILED: %d check(s)" % len(_failures), file=sys.stderr)
        return 1
    print("PASS: golden trace baseline comparator and approval flow (%d scenarios)" % len(SCENARIOS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
