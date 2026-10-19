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
import trace_replay as replay_module                       # noqa: E402
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
                  # Phase 1.29（M2）：新候选必须声明当前方案（与 approve candidate 产物一致）。
                  "candidate_fingerprint_scheme": approve.FINGERPRINT_SCHEME,
                  "candidate_fingerprint": approve.normalized_fingerprint(multi)},
        # Phase 1.30（E-2）：真实候选总是带 source.trace_run_id（build_candidate 从捕获写入），
        # 且必须与事件 run_id 一致——夹具照实反映，不再用「只有 captured_by」的候选。
        source={"captured_by": "unit-test real-baseline replay",
                "trace_run_id": "run-unit",
                "trace_event_count": len(real_multi["events"])},
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

    # Phase 1.26：锁定期间不可能成立出口胜利，因此“全清空后直接胜利、但没有解锁”
    # 先被回放层判为非法（victory_without_exit_unlock），比单纯的 EVENT_MISSING 更强。
    missing_exit = resequenced([x for x in waves_events()
                                if x["event_type"] != "exit_unlocked"])
    r = compare(waves_baseline, waves_trace_doc(missing_exit))
    ok("U61: dropping the exit unlock never passes (Phase 1.26: the replay layer"
       " rejects the unlock-less exit victory first)",
       r["exit_code"] == 1
       and (r["status"] == tb.STATUS_REGRESSION
            or r["status"] == tb.STATUS_INVALID_TRACE)
       and any("exit_unlocked" in str(d.get("actual"))
               or d["category"] == "EVENT_MISSING"
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

    # ==================== U64+. 已批准基线的真实事件链与批准可追溯性 ====================
    print()
    print("--- U64. approved baselines: real event chains and traceable approvals ---")
    approved_scenarios = ("multi_stage_boss", "single_stage_boss", "waves", "holdout")
    approved = {scenario: load_baseline(scenario) for scenario in approved_scenarios}
    waves_approved = approved["waves"]

    chain = [event["event_type"] for event in waves_approved["events"]]
    ok("U64: the approved waves baseline carries the full wave semantic chain"
       " (started → wave0 → clear → wave1 → clear → unlock → victory)",
       chain == ["orchestration_started", "wave_started", "wave_cleared",
                 "wave_started", "wave_cleared", "exit_unlocked", "level_victory"]
       and [event["reason"] for event in waves_approved["events"]][-2:]
       == ["all_waves_cleared", "exit_reached_after_unlock"],
       repr(chain))

    coverage_text = " ".join(waves_approved.get("coverage") or [])
    ok("U65: the waves baseline coverage no longer claims the trace lacks wave events"
       " and names the real event chain instead",
       "不含波次事件" not in coverage_text and "wave_started" in coverage_text
       and "exit_unlocked" in coverage_text, coverage_text[:160])

    schemes = {scenario: approve.matching_fingerprint_schemes(document)
               for scenario, document in approved.items()}
    ok("U66: every approved baseline's recorded fingerprint verifies under a"
       " documented scheme (approval record matches the actual content)",
       all(schemes[scenario] for scenario in approved_scenarios), repr(schemes))
    ok("U67: historical Phase 1.23 baselines verify under the legacy scheme (1)"
       " while Phase 1.24+ baselines verify under the current scheme (2)",
       schemes["multi_stage_boss"] == [1] and schemes["single_stage_boss"] == [1]
       and schemes["waves"] == [2] and schemes["holdout"] == [2]
       and approve.FINGERPRINT_SCHEME == 2, repr(schemes))

    ok("U68: the approved waves baseline compares PASS against its own real events",
       compare(waves_approved, real_trace(waves_approved))["status"] == tb.STATUS_PASS,
       repr(compare(waves_approved, real_trace(waves_approved))["differences"][:2]))

    # 回放仍然合法，但波次配置语义变了 → REGRESSION（逐事件差异，不是仅比数量）
    mutated_waves = real_trace(waves_approved)
    for event in mutated_waves["events"]:
        if event["event_type"] == "wave_started" and event["data"].get("wave") == 1:
            event["data"]["enemies"] = 99
    r = compare(waves_approved, mutated_waves)
    ok("U69: changing a wave composition field is REGRESSION with DATA_FIELD_CHANGED"
       " and a concrete field path (exit 1)",
       r["status"] == tb.STATUS_REGRESSION and r["exit_code"] == 1
       and any(difference["category"] == "DATA_FIELD_CHANGED"
               and ".data.enemies" in str(difference["field_path"])
               for difference in r["differences"]), r["summary"])

    renamed_reason = real_trace(waves_approved)
    renamed_reason["events"][-1]["reason"] = "forced"
    r = compare(waves_approved, renamed_reason)
    ok("U70: changing the waves terminal reason is REGRESSION (REASON_CHANGED, exit 1)",
       r["status"] == tb.STATUS_REGRESSION and r["exit_code"] == 1
       and any(difference["category"] == "REASON_CHANGED"
               for difference in r["differences"]), r["summary"])

    # ==================== U71+. holdout v2：生成调度激活的逐事件保护 ====================
    print()
    print("--- U71. holdout v2 spawn schedule coverage ---")
    holdout_approved = approved["holdout"]
    holdout_chain = [event["event_type"] for event in holdout_approved["events"]]
    ok("U71: the approved holdout baseline carries the spawn schedule chain"
       " (started → schedule 0 → victory)",
       holdout_chain == ["orchestration_started", "spawn_schedule_started",
                         "level_victory"]
       and int(holdout_approved["events"][1]["data"]["schedule"]) == 0
       and holdout_approved["baseline_version"] >= 2, repr(holdout_chain))
    holdout_coverage = " ".join(holdout_approved.get("coverage") or [])
    ok("U72: the holdout coverage names the spawn event as trace-level protection"
       " and keeps probe assertions separate",
       "spawn_schedule_started" in holdout_coverage
       and "事件级保护" in holdout_coverage
       and "探针度量断言（不是 trace 事件）" in holdout_coverage,
       holdout_coverage[:160])
    ok("U73: holdout v2 compares PASS against its own real events",
       compare(holdout_approved, real_trace(holdout_approved))["status"] == tb.STATUS_PASS,
       repr(compare(holdout_approved, real_trace(holdout_approved))["differences"][:2]))

    def retrace(trace: dict, events: list) -> dict:
        """换掉事件流并同步 event_count（否则会被判成截断的 trace）。"""
        trace["events"] = resequence(events)
        trace["event_count"] = len(trace["events"])
        return trace

    legacy_holdout = retrace(real_trace(holdout_approved),
                             [event for event in real_trace(holdout_approved)["events"]
                              if event["event_type"] != "spawn_schedule_started"])
    r = compare(holdout_approved, legacy_holdout)
    ok("U74: a legacy v1-shaped holdout trace (no spawn event) fails as EVENT_MISSING"
       " with exit 1 — it can no longer be accepted as the approved behaviour",
       r["status"] == tb.STATUS_REGRESSION and r["exit_code"] == 1
       and any(difference["category"] == "EVENT_MISSING"
               and "spawn_schedule_started" in str(difference.get("expected"))
               for difference in r["differences"]), r["summary"])

    mutated_schedule = real_trace(holdout_approved)
    mutated_schedule["events"][1]["data"]["interval"] = 9.9
    r = compare(holdout_approved, mutated_schedule)
    ok("U75: changing the spawn interval is REGRESSION (DATA_FIELD_CHANGED, exit 1)",
       r["status"] == tb.STATUS_REGRESSION and r["exit_code"] == 1
       and any(difference["category"] == "DATA_FIELD_CHANGED"
               and ".data.interval" in str(difference["field_path"])
               for difference in r["differences"]), r["summary"])

    duplicated_schedule = real_trace(holdout_approved)
    duplicate_event = dict(duplicated_schedule["events"][1], timestamp_ms=999)
    duplicated_schedule = retrace(
        duplicated_schedule,
        [duplicated_schedule["events"][0], duplicated_schedule["events"][1],
         duplicate_event, duplicated_schedule["events"][2]])
    r = compare(holdout_approved, duplicated_schedule)
    ok("U76: a duplicated spawn schedule event fails (TRACE_INVALID from the replay"
       " layer: duplicate_spawn_schedule)",
       r["exit_code"] == 1 and r["status"] == tb.STATUS_INVALID_TRACE
       and any("duplicate_spawn_schedule" in str(difference.get("field_path"))
               and difference.get("sequence") == 2
               for difference in r["differences"]),
       repr([(difference["category"], str(difference.get("actual"))[:60])
             for difference in r["differences"][:2]]))

    # ==================== U77+. 跨模式语义：回放器与比较器的一致结果 ====================
    print()
    print("--- U77. cross-mode semantics agree across replay and comparator (Phase 1.28) ---")

    def injected(event_type: str, **extra) -> dict:
        """构造一条形状合法的事件，供注入真实事件链（形状错误不得成为拒绝理由）。"""
        record = {
            "schema_version": tb.TRACE_SCHEMA_VERSION, "run_id": "run-inject",
            "sequence": 0, "timestamp_ms": 0, "event_type": event_type,
            "stage_id": None, "stage_index": None, "entity_id": None,
            "instance_name": None, "source": "orchestrator", "reason": "code", "data": {},
        }
        record.update(extra)
        return record

    def injection_trace(baseline: dict, new_event: dict, index: int = 1) -> dict:
        """把模式外事件注入真实事件链；同步 run_id / 序号 / 时间戳与 event_count。

        形状层错误会先于回放报告，因此这里只留语义错误作证据。
        """
        trace = real_trace(baseline, run_id="run-inject")
        events = copy.deepcopy(trace["events"])
        events.insert(index, dict(copy.deepcopy(new_event), run_id=trace["run_id"]))
        resequence(events)
        for position, event in enumerate(events):
            event["timestamp_ms"] = position
        trace["events"] = events
        trace["event_count"] = len(events)
        return trace

    def consistent_on(label: str, baseline: dict, trace: dict, reason: str) -> None:
        """同一非法语义必须在回放器与比较器给出同一可解释理由（否则证据互相矛盾）。"""
        replay_result = replay_module.replay(trace["events"])
        comparison = compare(baseline, trace)
        detail = repr({"replay": [error["reason"] for error in replay_result["errors"]][:2],
                       "status": comparison["status"], "exit": comparison["exit_code"],
                       "paths": [str(difference.get("field_path"))
                                 for difference in comparison["differences"]][:2]})
        ok(label,
           not replay_result["ok"]
           and reason in [error["reason"] for error in replay_result["errors"]]
           and comparison["status"] == tb.STATUS_INVALID_TRACE
           and comparison["exit_code"] == 1
           and any(reason in str(difference.get("field_path"))
                   or reason in str(difference.get("actual"))
                   for difference in comparison["differences"]), detail)

    consistent_on("U77: a waves-only event inside a boss trace is rejected by both layers"
                  " (wave_event_outside_waves_mode)", multi,
                  injection_trace(multi, injected("wave_started", reason="wave_begin",
                                                  data={"wave": 0, "total": 1,
                                                        "enemies": 1})),
                  "wave_event_outside_waves_mode")

    consistent_on("U78: a stage event inside a waves trace is rejected by both layers"
                  " (stage_event_outside_boss_stages)", waves_approved,
                  injection_trace(waves_approved, injected("stage_started", reason="clear_enemies",
                                                           stage_id="clear_1", stage_index=0,
                                                           data={"stage_type": "clear_enemies"})),
                  "stage_event_outside_boss_stages")

    consistent_on("U79: a holdout-only spawn event inside a boss trace is rejected by both layers"
                  " (spawn_event_outside_holdout_mode)", single,
                  injection_trace(single, injected("spawn_schedule_started", reason="spawn_due",
                                                   data={"schedule": 0, "entity": "enemy",
                                                         "interval": 0.3, "max_alive": 0})),
                  "spawn_event_outside_holdout_mode")

    consistent_on("U80: a boss-only death confirmation inside a waves trace is rejected by both"
                  " layers (boss_death_outside_boss_mode)", waves_approved,
                  injection_trace(waves_approved, injected("boss_death_confirmed",
                                                           reason="health_died",
                                                           entity_id="boss",
                                                           instance_name="Boss")),
                  "boss_death_outside_boss_mode")

    wrong_reason = real_trace(holdout_approved)
    wrong_reason["events"][-1]["reason"] = "boss_defeated"
    consistent_on("U81: a terminal reason outside the mode's reachable set is rejected by both"
                  " layers (victory_reason_outside_mode)", holdout_approved, wrong_reason,
                  "victory_reason_outside_mode")

    undeclared_mode = real_trace(multi)
    undeclared_mode["events"][0]["data"].pop("mode", None)
    consistent_on("U82: an undeclared orchestration mode is rejected by both layers"
                  " (invalid_start_mode) instead of disabling every mode gate", multi,
                  undeclared_mode, "invalid_start_mode")

    # 基线侧：结构合法但语义不合法的基线必须先被拒，不得把责任推给真实 trace
    forged_holdout = copy.deepcopy(holdout_approved)
    forged_holdout["events"][1] = injected("stage_started", reason="clear_enemies",
                                           stage_id="clear_1", stage_index=0,
                                           data={"stage_type": "clear_enemies"})
    forged_holdout["events"][1]["run_id"] = forged_holdout["events"][0]["run_id"]
    forged_events = copy.deepcopy(forged_holdout["events"])
    for position, event in enumerate(forged_events):
        event["sequence"] = position
        event["timestamp_ms"] = position
    forged_holdout["events"] = forged_events
    forged_errors = tb.validate_baseline(forged_holdout)
    forged_result = compare(forged_holdout, real_trace(holdout_approved))
    ok("U83: a baseline whose events cannot replay is INVALID_BASELINE (exit 2) with the"
       " replay reason, and the real trace is not blamed",
       any("events must replay" in error and "stage_event_outside_boss_stages" in error
           for error in forged_errors)
       and forged_result["status"] == tb.STATUS_INVALID_BASELINE
       and forged_result["exit_code"] == 2
       and any(difference["category"] == "BASELINE_INVALID"
               for difference in forged_result["differences"]),
       repr({"errors": forged_errors[:1], "status": forged_result["status"],
             "exit": forged_result["exit_code"]}))

    # 兼容性与模式边界守护：四个真实基线的事件类型只能落在公共集 + 各自模式专属集内
    common_types = {"orchestration_started", "level_victory", "level_failed",
                    "duplicate_event_ignored", "invalid_transition_rejected"}
    exclusive_types = {
        "boss": {"stage_started", "stage_completed", "stage_transitioned",
                 "boss_death_confirmed"},
        "waves": {"wave_started", "wave_cleared", "exit_unlocked"},
        "holdout": {"spawn_schedule_started"},
    }
    matrix_report = {}
    for scenario, document in approved.items():
        mode = document["events"][0]["data"].get("mode")
        observed = {event["event_type"] for event in document["events"]}
        matrix_report[scenario] = (mode, sorted(observed - common_types - exclusive_types.get(mode or "", set())))
    ok("U84: every approved baseline replays and carries only its own mode's exclusive"
       " events (no cross-mode leakage in the golden set)",
       all(not tb.validate_baseline(document)
           and replay_module.replay(document["events"])["ok"]
           and compare(document, real_trace(document))["status"] == tb.STATUS_PASS
           and not matrix_report[scenario][1]
           for scenario, document in approved.items()), repr(matrix_report))

    consistent_on("U85: a waves-only event inside a holdout trace is rejected by both layers"
                  " (wave_event_outside_waves_mode)", holdout_approved,
                  injection_trace(holdout_approved, injected("wave_started",
                                                              reason="wave_begin",
                                                              data={"wave": 0, "total": 1,
                                                                    "enemies": 1})),
                  "wave_event_outside_waves_mode")

    # ==================== U86+. 审批入口的信任边界（Phase 1.29） ====================
    print()
    print("--- U86. approval entry trust boundary (Phase 1.29) ---")

    with tempfile.TemporaryDirectory(prefix="trace_baseline_boundary_") as raw:
        boundary_dir = Path(raw)
        boundary_dir.joinpath("candidates").mkdir()
        boundary_baseline = boundary_dir / "multi_stage_boss.json"   # 不存在：此段只验证拒绝

        # M2：缺少指纹方案声明的候选不得被批准（否则 apply 会按当前方案写入记录，
        # 而指纹实际由已废弃的 scheme 1 算出 → 批准记录永远无法复算）。
        no_scheme = copy.deepcopy(candidate)
        no_scheme["approval"].pop("candidate_fingerprint_scheme", None)
        no_scheme["approval"]["candidate_fingerprint"] = approve.normalized_fingerprint(no_scheme, 1)
        no_scheme_path = write_json(boundary_dir / "candidates" / "no_scheme.candidate.json",
                                    no_scheme)
        no_scheme_errors = approve.verify_candidate_fingerprint(no_scheme)
        ok("U86: a candidate that does not declare its fingerprint scheme is rejected"
           " (scheme 1 may only verify historical baselines)",
           any("candidate_fingerprint_scheme" in error
               and "historical baselines" in error for error in no_scheme_errors)
           and approve.main(["apply", "--candidate", str(no_scheme_path),
                             "--baseline-dir", str(boundary_dir), "--approver", "reviewer",
                             "--note", "unit", "--i-approve"]) == 1
           and not boundary_baseline.exists(),
           repr(no_scheme_errors[:2]))

        # M2：明确声明已废弃方案的候选同样不得被批准。
        legacy_scheme = copy.deepcopy(candidate)
        legacy_scheme["approval"]["candidate_fingerprint_scheme"] = 1
        legacy_scheme["approval"]["candidate_fingerprint"] = \
            approve.normalized_fingerprint(legacy_scheme, 1)
        legacy_path = write_json(boundary_dir / "candidates" / "legacy_scheme.candidate.json",
                                 legacy_scheme)
        legacy_errors = approve.verify_candidate_fingerprint(legacy_scheme)
        ok("U87: a candidate declaring the deprecated fingerprint scheme is rejected"
           " (exit 1, baseline untouched)",
           any("new approvals must use scheme" in error for error in legacy_errors)
           and approve.main(["apply", "--candidate", str(legacy_path),
                             "--baseline-dir", str(boundary_dir), "--approver", "reviewer",
                             "--note", "unit", "--i-approve"]) == 1
           and not boundary_baseline.exists(),
           repr(legacy_errors[:2]))

        # L1：--scenario 与候选内容身份不一致时拒绝（写入目标跟随内容，不能让 CLI 声明被忽略）。
        # 文件名声称 waves，内容却是 multi_stage_boss：目录解析命中该文件后，身份校验应拒绝。
        mislabelled = copy.deepcopy(candidate)
        mislabelled["approval"]["candidate_fingerprint"] = \
            approve.normalized_fingerprint(mislabelled)
        mislabelled_dir = boundary_dir / "mislabelled"
        mislabelled_dir.mkdir()
        mislabelled_path = write_json(mislabelled_dir / "waves.candidate.json", mislabelled)
        _doc, identity_error, identity_code = approve.load_candidate(mislabelled_path, "waves")
        mismatch_apply = approve.main(["apply", "--candidate", str(mislabelled_dir),
                                       "--scenario", "waves", "--baseline-dir", str(boundary_dir),
                                       "--approver", "reviewer", "--note", "unit", "--i-approve"])
        ok("U88: a candidate whose content disagrees with --scenario is rejected as a"
           " mislabelled input error (exit 2, nothing written)",
           identity_code == 2 and "mislabelled" in identity_error
           and mismatch_apply == 2 and not boundary_baseline.exists(),
           repr({"code": identity_code, "error": identity_error[:90], "apply": mismatch_apply}))
        mismatch_review = approve.main(["review", "--candidate", str(mislabelled_path),
                                        "--scenario", "waves", "--baseline-dir", str(boundary_dir)])
        matching_review = approve.main(["review", "--candidate", str(mislabelled_path),
                                        "--scenario", "multi_stage_boss",
                                        "--baseline-dir", str(boundary_dir)])
        ok("U89: review applies the same identity check as apply, and a truthful --scenario"
           " still passes (positive control for the new guard)",
           mismatch_review == 2 and matching_review == 0
           and not list(boundary_dir.glob("*.json")),
           repr({"mismatch": mismatch_review, "matching": matching_review,
                 "written": [str(p) for p in boundary_dir.glob("*.json")]}))

        # L2：不可读 / 非法 JSON 的候选在两个入口给出一致诊断与非零退出码（不抛异常）。
        broken_candidate = boundary_dir / "candidates" / "broken.candidate.json"
        broken_candidate.write_text("{not json", encoding="utf-8")
        apply_code = approve.main(["apply", "--candidate", str(broken_candidate),
                                   "--baseline-dir", str(boundary_dir), "--approver", "reviewer",
                                   "--note", "unit", "--i-approve"])
        review_code = approve.main(["review", "--candidate", str(broken_candidate),
                                    "--baseline-dir", str(boundary_dir)])
        ok("U90: an unreadable candidate is a clean input error in both entries (exit 2,"
           " no traceback, nothing written)",
           apply_code == 2 and review_code == 2 and not boundary_baseline.exists(),
           "apply=%s review=%s" % (apply_code, review_code))

    # ==================== U91+. 输入类错误的分类与退出码（Phase 1.29 M3 锁定） ====================
    print()
    print("--- U91. input-class verdicts and exit codes (Phase 1.29 M3 lock) ---")

    with tempfile.TemporaryDirectory(prefix="trace_baseline_inputs_") as raw:
        inputs = Path(raw)
        missing_trace = inputs / "no_such_trace.json"
        malformed_trace = inputs / "malformed_trace.json"
        malformed_trace.write_text("{not json", encoding="utf-8")
        malformed_baseline = inputs / "malformed_baseline.json"
        malformed_baseline.write_text("[1, 2, 3", encoding="utf-8")

        missing_trace_result = tb.compare_files(missing_trace, tb.baseline_path_for("multi_stage_boss"))
        malformed_trace_result = tb.compare_files(malformed_trace,
                                                  tb.baseline_path_for("multi_stage_boss"))
        ok("U91: an unreadable trace is INVALID_TRACE (exit 1) with a diagnostic naming the"
           " input, never PASS",
           missing_trace_result["status"] == tb.STATUS_INVALID_TRACE
           and missing_trace_result["exit_code"] == 1
           and any(difference["category"] == "TRACE_INVALID"
                   and "no_such_trace.json" in str(difference.get("actual"))
                   for difference in missing_trace_result["differences"])
           and malformed_trace_result["status"] == tb.STATUS_INVALID_TRACE
           and malformed_trace_result["exit_code"] == 1,
           repr([missing_trace_result["status"], malformed_trace_result["status"]]))

        malformed_baseline_result = tb.compare_files(
            tb.baseline_path_for("multi_stage_boss"), malformed_baseline)
        missing_baseline_result = tb.compare_files(tb.baseline_path_for("multi_stage_boss"),
                                                   inputs / "no_such_baseline.json")
        ok("U92: a missing / unreadable baseline is BASELINE_MISSING / INVALID_BASELINE"
           " (both exit 2) and never PASS",
           missing_baseline_result["status"] == tb.STATUS_BASELINE_MISSING
           and missing_baseline_result["exit_code"] == 2
           and malformed_baseline_result["status"] == tb.STATUS_INVALID_BASELINE
           and malformed_baseline_result["exit_code"] == 2,
           repr([missing_baseline_result["status"], malformed_baseline_result["status"]]))

        # 跨入口差异：同一「文件不存在」在只读回放 CLI 是输入错误 2，在本比较入口是 1。
        # Phase 1.29 审计结论 M3：保持现有映射（CLI 兼容）、文档化并用此测试锁定，
        # 不得因“统一字符串/码”而静默改变任一入口的行为。
        replay_cli_code = replay_module.main([str(inputs / "nope.json")])
        ok("U93: the documented cross-entry difference is locked: replay CLI input error = 2,"
           " comparator unreadable trace = 1 (both non-zero, neither is PASS)",
           replay_cli_code == 2 and missing_trace_result["exit_code"] == 1
           and "INVALID_TRACE" in (tb.compare_files.__doc__ or "")
           and "BASELINE_MISSING" in (tb.compare_files.__doc__ or ""),
           repr({"replay_cli": replay_cli_code, "comparator": missing_trace_result["exit_code"]}))

    # ==================== U94. 审批正常路径闭环（Phase 1.29） ====================
    class _StubCapture:
        """代替代价高的真实沙箱捕获（真实捕获由 E2E T5 覆盖），只验证审批链本身。"""
        ok = True
        error = ""
        evidence = {"description": "unit stub capture", "coverage": ["unit stub"],
                    "captured_by": None, "godot_version": "stub", "probe": "stub",
                    "level_config": "stub"}
        trace_document = real_trace(multi)

    with tempfile.TemporaryDirectory(prefix="trace_baseline_chain_") as raw:
        chain_dir = Path(raw)
        chain_candidates = chain_dir / "candidates"
        chain_candidates.mkdir()
        chain_baselines = chain_dir / "baselines"
        chain_baselines.mkdir()
        original_capture = approve.trace_baseline_capture.capture
        try:
            approve.trace_baseline_capture.capture = lambda *args, **kwargs: _StubCapture()
            generated = approve.main(["candidate", "--scenario", "multi_stage_boss",
                                      "--out", str(chain_candidates), "--note", "unit chain"])
        finally:
            approve.trace_baseline_capture.capture = original_capture
        generated_path = chain_candidates / "multi_stage_boss.candidate.json"
        reviewed = approve.main(["review", "--candidate", str(generated_path),
                                 "--baseline-dir", str(chain_baselines)])
        applied_chain = approve.main(["apply", "--candidate", str(generated_path),
                                      "--baseline-dir", str(chain_baselines),
                                      "--approver", "reviewer", "--note", "unit chain",
                                      "--i-approve"])
        approved_chain = json.loads((chain_baselines / "multi_stage_boss.json").read_text(
            encoding="utf-8")) if (chain_baselines / "multi_stage_boss.json").is_file() else {}
        ok("U94: the tool's own candidate output still completes candidate → review → apply,"
           " and the approved record's declared scheme recomputes its content"
           " (normal path unaffected by the Phase 1.29 hardening)",
           generated == 0 and reviewed == 0 and applied_chain == 0
           and approve.matching_fingerprint_schemes(approved_chain) == [approve.FINGERPRINT_SCHEME]
           and approved_chain.get("approval", {}).get("status") == "approved",
           repr({"candidate": generated, "review": reviewed, "apply": applied_chain,
                 "schemes": approve.matching_fingerprint_schemes(approved_chain)}))

    # ==================== U95+. 证据来源一致性（Phase 1.30） ====================
    print("--- U95. evidence provenance consistency (Phase 1.30) ---")
    provenance = tb.build_baseline(
        real_multi, scenario_id="multi_stage_boss",
        scenario_description=multi["scenario_description"],
        approved_behavior_version=multi["approved_behavior_version"],
        approval={"status": "candidate", "candidate_generated_at": "2026-10-19T00:00:00",
                  "candidate_fingerprint_scheme": approve.FINGERPRINT_SCHEME},
        source={"captured_by": "unit-test real-baseline replay",
                "trace_run_id": "run-unit",
                "trace_event_count": len(real_multi["events"])},
        coverage=multi["coverage"])
    provenance["approval"]["candidate_fingerprint"] = approve.normalized_fingerprint(provenance)
    runs_before = [event["run_id"] for event in provenance["events"]]
    provenance_errors = approve._validate_candidate(provenance)
    runs_after = [event["run_id"] for event in provenance["events"]]
    ok("U95: candidate validation accepts a self-consistent candidate and does NOT rewrite"
       " the caller's event run_id (Phase 1.30 E-1: previously it became 'candidate-check')",
       not provenance_errors and runs_before == runs_after
       and set(runs_after) == {"run-unit"},
       repr({"errors": provenance_errors, "before": sorted(set(runs_before)),
             "after": sorted(set(runs_after))}))

    stolen_run = copy.deepcopy(provenance)
    stolen_run["source"]["trace_run_id"] = "run-someone-else"
    stolen_errors = approve._validate_candidate(stolen_run)
    ok("U96: a candidate whose declared run does not match its events is rejected"
       " (source.trace_run_id is a consistency claim, not free text)",
       bool(stolen_errors) and any("trace_run_id" in error for error in stolen_errors),
       repr(stolen_errors))

    anonymous = copy.deepcopy(provenance)
    anonymous["source"].pop("trace_run_id", None)
    anonymous_errors = approve._validate_candidate(anonymous)
    ok("U97: a candidate without source.trace_run_id is rejected (its events cannot be tied"
       " to any run)",
       bool(anonymous_errors) and any("trace_run_id" in error for error in anonymous_errors),
       repr(anonymous_errors))

    truncated_count = copy.deepcopy(provenance)
    truncated_count["source"]["trace_event_count"] = len(provenance["events"]) + 1
    count_errors = approve._validate_candidate(truncated_count)
    # 截断捕获（少事件但仍报原始条数）同样必须被计数校验抓住——这是「捕获不完整」的信号。
    edited_events = copy.deepcopy(provenance)
    edited_events["events"] = edited_events["events"][:-1]
    edited_errors = approve._validate_candidate(edited_events)
    ok("U98: a candidate whose source.trace_event_count disagrees with its events is rejected"
       " (both a wrong count and a truncated event stream are caught)",
       bool(count_errors) and any("trace_event_count" in error for error in count_errors)
       and any("trace_event_count" in error for error in edited_errors),
       repr({"count": count_errors, "truncated": edited_errors}))

    with tempfile.TemporaryDirectory(prefix="trace_baseline_provenance_") as raw:
        prov_dir = Path(raw)
        prov_candidates = prov_dir / "candidates"
        prov_candidates.mkdir()
        prov_baselines = prov_dir / "baselines"
        prov_baselines.mkdir()
        prov_path = write_json(prov_candidates / "multi_stage_boss.candidate.json", provenance)
        applied_prov = approve.main(["apply", "--candidate", str(prov_path),
                                     "--baseline-dir", str(prov_baselines),
                                     "--approver", "reviewer", "--note", "provenance unit",
                                     "--i-approve"])
        written = json.loads((prov_baselines / "multi_stage_boss.json").read_text(
            encoding="utf-8")) if (prov_baselines / "multi_stage_boss.json").is_file() else {}
        written_runs = sorted({event.get("run_id") for event in written.get("events") or []})
        ok("U99: apply writes a baseline whose events keep the captured run_id and still match"
           " source.trace_run_id (the approval flow no longer destroys the evidence link)",
           applied_prov == 0 and written_runs == ["run-unit"]
           and written.get("source", {}).get("trace_run_id") == "run-unit"
           and approve.matching_fingerprint_schemes(written) == [approve.FINGERPRINT_SCHEME],
           repr({"exit": applied_prov, "event_run_ids": written_runs,
                 "source_run": written.get("source", {}).get("trace_run_id")}))

    ok("U48: the toolchain-approved baselines are untouched by this unit test",
       all(load_baseline(scenario) == baselines[scenario] for scenario in SCENARIOS)
       and all(load_baseline(scenario) == approved[scenario]
               for scenario in approved_scenarios))

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
