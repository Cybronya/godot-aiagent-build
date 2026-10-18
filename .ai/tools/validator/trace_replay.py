#!/usr/bin/env python3
"""Orchestration Trace Replay（Phase 1.22）

读取 `Orchestration/orchestration_trace.gd` 导出的诊断事件流（纯数据 JSON），按契约
**确定性重建**编排诊断状态，并报告第一条不合法事件：

    python .ai/tools/validator/trace_replay.py <trace.json> [--json]

边界（与真实状态机的职责划分）：
  - 本模块**只读**：不调用 Godot、不加载场景、不触发 finish_level / Boss 死亡 / 阶段转换；
  - “回放成功” = 事件流符合契约并能确定性重建状态，**不代表重新执行了游戏**；
  - 权威状态机仍是 `LevelOrchestrator`；本模块只校验事件流是否与状态机语义一致。

契约（`.ai/context/orchestration_trace_schema.yaml`）：
  - `schema_version == 1`（未知版本拒绝）；`document == "orchestration_trace"`；
  - `sequence` 从 0 起严格递增（+1，无重复 / 倒退 / 缺口）；
  - `timestamp_ms` 为非负、非递减的相对毫秒时间；
  - 首个事件必须是 `orchestration_started`；终结事件之后只允许 `duplicate_event_ignored`；
  - `level_victory` / `level_failed` 互斥；boss 模式的胜利必须先有 `boss_death_confirmed`；
  - 阶段推进必须按索引顺序（前一阶段完成后才能开始下一阶段）。

退出码: 0 = trace 合法且可回放；1 = trace 违反契约；2 = 输入错误（文件/JSON/schema 版本）。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

DOCUMENT = "orchestration_trace"
SCHEMA_VERSION = 1

KNOWN_TYPES = (
    "orchestration_started",
    "stage_started",
    "stage_completed",
    "stage_transitioned",
    "boss_death_confirmed",
    "level_victory",
    "level_failed",
    "duplicate_event_ignored",
    "invalid_transition_rejected",
    # Phase 1.25（v1 加性扩展）：waves 模式语义事件。旧 trace 不含这些类型，
    # 回放行为不变；新规则仅作用于含波次事件的 trace（向后兼容，见 schema 文档）。
    "wave_started",
    "wave_cleared",
    "exit_unlocked",
)
TERMINAL_TYPES = ("level_victory", "level_failed")
REQUIRED_FIELDS = (
    "schema_version", "run_id", "sequence", "event_type", "timestamp_ms",
    "stage_id", "stage_index", "source", "reason", "entity_id", "instance_name", "data",
)
STAGE_TYPES = ("stage_started", "stage_completed", "stage_transitioned")


class TraceInputError(ValueError):
    """trace 文件不可读 / 非法 JSON（CLI 退出码 2）。"""


def load_trace(path) -> dict:
    """读取 trace 文件并解析为 JSON 对象；失败抛 TraceInputError。"""
    path = Path(path)
    if not path.is_file():
        raise TraceInputError("trace file not found: %s" % path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TraceInputError("cannot read trace %s: %s" % (path, exc))
    try:
        document = json.loads(text)
    except ValueError as exc:
        raise TraceInputError("%s: invalid JSON: %s" % (path, exc))
    if not isinstance(document, dict):
        raise TraceInputError("%s: root must be a JSON object" % path)
    return document


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _error(errors: list, sequence, reason: str, message: str) -> None:
    errors.append({"sequence": sequence, "reason": reason, "message": message})


def _reject(errors: list, sequence, reason: str, message: str) -> None:
    """契约违例：记录后停止按状态机继续解释（同一 trace 的结果保持确定性）。"""
    _error(errors, sequence, reason, message)


def replay(events, *, run_id: str = "", event_count=None, dropped_events: int = 0,
           document=None) -> dict:
    """按契约回放事件序列；返回结构化结果（纯数据，确定性）。

    允许直接传入事件数组做单测（document=None）；此时不校验文档级字段。
    """
    errors: list = []
    ignored_events: list = []
    rejected_events: list = []
    started_stages: list = []
    completed_stages: list = []
    transitions: list = []
    event_summary: Counter = Counter()

    state = {
        "started": False,
        "mode": None,
        "stage_count": 0,
        "requires_boss_death": False,
        "boss_death": False,
        "terminal": None,
        "current": None,
        "last_started": None,
        "last_completed": None,
        "pending_expected": None,
        "sequence_gaps": 0,
        # Phase 1.25：waves 模式波次状态（仅当 trace 含波次事件时参与校验）
        "wave_total": None,           # 来自 wave_started.data.total（首次出现后固定）
        "wave_started_count": 0,      # 已开始的波次数（应为 data.wave + 1）
        "wave_current": None,         # 当前已开始、尚未清空的波次索引
        "wave_cleared_count": 0,
        "exit_unlocked": False,
    }

    if document is not None:
        if document.get("document") != DOCUMENT:
            _reject(errors, None, "invalid_document",
                    "document must be %r, got %r" % (DOCUMENT, document.get("document")))
        version = document.get("schema_version")
        if version != SCHEMA_VERSION:
            _reject(errors, None, "unsupported_schema_version",
                    "schema_version must be %d, got %r" % (SCHEMA_VERSION, version))
        document_run = str(document.get("run_id") or "")
        if run_id and document_run and run_id != document_run:
            _reject(errors, None, "run_id_mismatch",
                    "document run_id %r != requested %r" % (document_run, run_id))
        run_id = run_id or document_run
        if event_count is not None and _is_int(event_count) and event_count != len(events):
            _reject(errors, None, "truncated_trace",
                    "event_count=%d but %d events present" % (event_count, len(events)))
        if dropped_events:
            _reject(errors, None, "trace_incomplete",
                    "%d event(s) were dropped by the recorder" % dropped_events)

    if not events:
        _reject(errors, None, "empty_trace", "trace contains no events")
        return _result(errors, ignored_events, rejected_events, started_stages,
                       completed_stages, transitions, event_summary, state, run_id,
                       len(events))

    previous_sequence = -1
    previous_timestamp = -1.0
    fatal = False
    for raw_event in events:
        if fatal:
            break
        if not isinstance(raw_event, dict):
            _reject(errors, previous_sequence if previous_sequence >= 0 else None,
                    "invalid_event", "event must be a JSON object, got %r"
                    % type(raw_event).__name__)
            continue
        event = raw_event
        sequence = event.get("sequence") if _is_int(event.get("sequence")) else None
        missing = [field for field in REQUIRED_FIELDS if field not in event]
        if missing:
            _error(errors, sequence, "missing_field",
                   "missing required field(s): %s" % ", ".join(missing))
            continue
        if event.get("schema_version") != SCHEMA_VERSION:
            _reject(errors, sequence, "unsupported_schema_version",
                    "event schema_version must be %d, got %r"
                    % (SCHEMA_VERSION, event.get("schema_version")))
            fatal = True
            continue
        if not isinstance(event.get("run_id"), str) or not event.get("run_id"):
            _error(errors, sequence, "invalid_field",
                   "run_id must be a non-empty string")
        if run_id and event.get("run_id") != run_id:
            _error(errors, sequence, "run_id_mismatch",
                   "event run_id %r != trace run_id %r" % (event.get("run_id"), run_id))
        if not _is_int(sequence):
            _error(errors, None, "invalid_field", "sequence must be an integer")
            continue
        if sequence <= previous_sequence:
            _error(errors, sequence, "sequence_not_increasing",
                   "sequence %d must be strictly greater than %d"
                   % (sequence, previous_sequence))
            continue
        if sequence != previous_sequence + 1:
            _error(errors, sequence, "sequence_gap",
                   "sequence %d follows %d (missing events)" % (sequence, previous_sequence))
            state["sequence_gaps"] += 1
        previous_sequence = sequence
        timestamp = event.get("timestamp_ms")
        if not _is_number(timestamp) or timestamp < 0:
            _error(errors, sequence, "invalid_field",
                   "timestamp_ms must be a non-negative number")
        elif float(timestamp) < previous_timestamp:
            _error(errors, sequence, "timestamp_regressed",
                   "timestamp_ms %.3f is before %.3f"
                   % (float(timestamp), previous_timestamp))
        else:
            previous_timestamp = float(timestamp)
        if not isinstance(event.get("data"), dict):
            _error(errors, sequence, "invalid_field", "data must be an object")
        for field in ("source", "reason"):
            if not isinstance(event.get(field), str) or not event.get(field):
                _error(errors, sequence, "invalid_field",
                       "%s must be a non-empty string" % field)
        for field in ("stage_id", "entity_id", "instance_name"):
            if event.get(field) is not None and not isinstance(event.get(field), str):
                _error(errors, sequence, "invalid_field",
                       "%s must be a string or null" % field)
        if event.get("stage_index") is not None and not _is_int(event.get("stage_index")):
            _error(errors, sequence, "invalid_field",
                   "stage_index must be an integer or null")
        event_type = str(event.get("event_type"))
        if event_type not in KNOWN_TYPES:
            _reject(errors, sequence, "unknown_event_type",
                    "unknown event_type %r" % event_type)
            continue
        event_summary[event_type] += 1

        if state["terminal"] is not None:
            if event_type in TERMINAL_TYPES:
                reason = ("duplicate_terminal" if event_type == state["terminal"]
                          else "conflicting_terminal")
                _reject(errors, sequence, reason,
                        "%s after %s" % (event_type, state["terminal"]))
            elif event_type != "duplicate_event_ignored":
                _reject(errors, sequence, "event_after_terminal",
                        "%s is not allowed after %s" % (event_type, state["terminal"]))
            else:
                ignored_events.append({"sequence": sequence,
                                       "reason": str(event.get("reason"))})
            continue

        if not state["started"] and event_type != "orchestration_started":
            _reject(errors, sequence, "missing_start",
                    "first event must be orchestration_started, got %s" % event_type)
            fatal = True
            continue

        if event_type == "orchestration_started":
            if state["started"]:
                _reject(errors, sequence, "duplicate_start",
                        "orchestration_started must appear exactly once")
                continue
            state["started"] = True
            data = event.get("data") or {}
            state["mode"] = data.get("mode")
            stage_count = data.get("stage_count", 0)
            state["stage_count"] = int(stage_count) if _is_int(stage_count) else 0
            state["requires_boss_death"] = state["mode"] == "boss"
        elif event_type == "stage_started":
            index = event.get("stage_index")
            stage_id = event.get("stage_id")
            if not _is_int(index) or not isinstance(stage_id, str) or not stage_id:
                _reject(errors, sequence, "invalid_stage_event",
                        "stage_started requires stage_id and integer stage_index")
                continue
            if state["current"] is not None:
                _reject(errors, sequence, "stage_start_before_completion",
                        "stage %s started before stage %s completed"
                        % (stage_id, state["current"]["stage_id"]))
                continue
            pending = state["pending_expected"]
            if pending is not None and (stage_id, index) != pending:
                _reject(errors, sequence, "transition_stage_mismatch",
                        "stage_transitioned declared %r but stage_started is %r"
                        % (pending, (stage_id, index)))
                continue
            expected_index = len(started_stages)
            if index != expected_index:
                _reject(errors, sequence, "stage_start_out_of_order",
                        "stage index %d started while %d was expected"
                        % (index, expected_index))
                continue
            state["pending_expected"] = None
            state["current"] = {"stage_id": stage_id, "stage_index": index}
            state["last_started"] = state["current"]
            started_stages.append(dict(state["current"]))
        elif event_type == "stage_completed":
            index = event.get("stage_index")
            stage_id = event.get("stage_id")
            current = state["current"]
            if current is None:
                reason = ("duplicate_stage_completion"
                          if state["last_completed"] is not None
                          and index == state["last_completed"]["stage_index"]
                          else "stage_completed_without_start")
                _reject(errors, sequence, reason,
                        "stage_completed has no active stage (index=%r)" % index)
                continue
            if index != current["stage_index"] or stage_id != current["stage_id"]:
                _reject(errors, sequence, "stage_completed_mismatch",
                        "stage_completed %r does not match active stage %r"
                        % ((stage_id, index), (current["stage_id"], current["stage_index"])))
                continue
            completed_stages.append(dict(current))
            state["last_completed"] = dict(current)
            state["current"] = None
        elif event_type == "stage_transitioned":
            data = event.get("data") or {}
            from_id = data.get("from_stage_id")
            from_index = data.get("from_stage_index")
            to_id = data.get("to_stage_id")
            to_index = data.get("to_stage_index")
            last_completed = state["last_completed"]
            if last_completed is None or state["current"] is not None:
                _reject(errors, sequence, "transition_without_completion",
                        "stage_transitioned requires a freshly completed stage")
                continue
            if from_id != last_completed["stage_id"] \
                    or from_index != last_completed["stage_index"]:
                _reject(errors, sequence, "transition_source_mismatch",
                        "transition from %r %r, last completed %r"
                        % (from_id, from_index, last_completed))
                continue
            if to_id is None and to_index is None:
                state["pending_expected"] = None
            elif isinstance(to_id, str) and to_id and _is_int(to_index):
                state["pending_expected"] = (to_id, to_index)
            else:
                _reject(errors, sequence, "invalid_transition_target",
                        "to_stage_id/to_stage_index must both be null or a stage identity")
                continue
            transitions.append({"sequence": sequence, "from": from_id, "from_index": from_index,
                                "to": to_id, "to_index": to_index,
                                "reason": event.get("reason")})
        elif event_type == "boss_death_confirmed":
            if state["boss_death"]:
                _reject(errors, sequence, "duplicate_boss_death",
                        "boss_death_confirmed must appear at most once")
                continue
            if state["mode"] is not None and state["mode"] != "boss":
                _reject(errors, sequence, "boss_death_outside_boss_mode",
                        "boss death confirmed while mode=%r" % state["mode"])
                continue
            state["boss_death"] = True
        elif event_type in ("wave_started", "wave_cleared", "exit_unlocked"):
            data = event.get("data") or {}
            # 语义约束：波次事件只属于 waves 模式（mode 来自 orchestration_started）。
            if state["mode"] is not None and state["mode"] != "waves":
                _reject(errors, sequence, "wave_event_outside_waves_mode",
                        "%s while mode=%r" % (event_type, state["mode"]))
                continue
            for field_name in ("stage_id", "stage_index", "entity_id", "instance_name"):
                if event.get(field_name) is not None:
                    _reject(errors, sequence, "invalid_wave_event",
                            "%s must not carry %s (waves have no stage identity)"
                            % (event_type, field_name))
                    break
            else:
                if event_type == "wave_started":
                    wave = data.get("wave")
                    total = data.get("total")
                    if not _is_int(wave) or not _is_int(total) or total <= 0:
                        _reject(errors, sequence, "invalid_wave_event",
                                "wave_started requires integer data.wave and positive"
                                " data.total (got %r/%r)" % (wave, total))
                        continue
                    if state["wave_total"] is not None and total != state["wave_total"]:
                        _reject(errors, sequence, "wave_total_mismatch",
                                "data.total %r contradicts earlier %r"
                                % (total, state["wave_total"]))
                        continue
                    if state["wave_total"] is None:
                        state["wave_total"] = total
                    if state["wave_current"] is not None:
                        _reject(errors, sequence, "wave_start_before_clear",
                                "wave %d started while wave %d was not cleared"
                                % (wave, state["wave_current"]))
                        continue
                    if wave != state["wave_started_count"]:
                        _reject(errors, sequence, "wave_start_out_of_order",
                                "wave %d started while wave %d was expected"
                                % (wave, state["wave_started_count"]))
                        continue
                    state["wave_started_count"] += 1
                    state["wave_current"] = wave
                elif event_type == "wave_cleared":
                    wave = data.get("wave")
                    if not _is_int(wave):
                        _reject(errors, sequence, "invalid_wave_event",
                                "wave_cleared requires integer data.wave (got %r)" % (wave,))
                        continue
                    if state["wave_current"] is None or wave != state["wave_current"]:
                        _reject(errors, sequence, "wave_clear_mismatch",
                                "wave_cleared %r does not match the active wave %r"
                                % (wave, state["wave_current"]))
                        continue
                    state["wave_current"] = None
                    state["wave_cleared_count"] += 1
                else:  # exit_unlocked
                    if state["exit_unlocked"]:
                        _reject(errors, sequence, "duplicate_exit_unlock",
                                "exit_unlocked must appear at most once")
                        continue
                    if state["wave_total"] is None                             or state["wave_cleared_count"] != state["wave_total"]:
                        _reject(errors, sequence, "exit_unlocked_before_final_clear",
                                "exit_unlocked requires all %r waves cleared "
                                "(cleared=%r)" % (state["wave_total"],
                                                  state["wave_cleared_count"]))
                        continue
                    state["exit_unlocked"] = True
        elif event_type == "duplicate_event_ignored":
            ignored_events.append({"sequence": sequence, "reason": str(event.get("reason"))})
        elif event_type == "invalid_transition_rejected":
            rejected_events.append({"sequence": sequence, "reason": str(event.get("reason"))})
        elif event_type == "level_victory":
            if state["requires_boss_death"] and not state["boss_death"]:
                _reject(errors, sequence, "victory_without_boss_death",
                        "boss-mode victory requires boss_death_confirmed first")
                continue
            if state["stage_count"] and len(completed_stages) < state["stage_count"]:
                _reject(errors, sequence, "victory_before_all_stages",
                        "victory with %d/%d stages completed"
                        % (len(completed_stages), state["stage_count"]))
                continue
            # Phase 1.25：waves 模式且 trace 含波次事件（total 已知）时，
            # 胜利前必须清完全部波次（exit_reached 与 all_waves_cleared 皆然）。
            if state["mode"] == "waves" and state["wave_total"] is not None \
                    and state["wave_cleared_count"] != state["wave_total"]:
                _reject(errors, sequence, "victory_before_all_waves_cleared",
                        "waves victory with %d/%d waves cleared"
                        % (state["wave_cleared_count"], state["wave_total"]))
                continue
            state["terminal"] = event_type
        elif event_type == "level_failed":
            state["terminal"] = event_type

    current = state["current"] or state["last_started"]
    return _result(errors, ignored_events, rejected_events, started_stages,
                   completed_stages, transitions, event_summary, state, run_id,
                   len(events), current=current)


def _result(errors, ignored_events, rejected_events, started_stages, completed_stages,
            transitions, event_summary, state, run_id, events_processed, current=None) -> dict:
    terminal = state["terminal"]
    final_state = "victory" if terminal == "level_victory" else \
        "failed" if terminal == "level_failed" else \
        "playing" if state["started"] else "empty"
    current = current or state.get("current") or state.get("last_started")
    return {
        "ok": not errors,
        "document": DOCUMENT,
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "mode": state["mode"],
        "final_state": final_state,
        "current_stage_id": current["stage_id"] if current else None,
        "current_stage_index": current["stage_index"] if current else None,
        "started_stages": started_stages,
        "completed_stages": completed_stages,
        "transitions": transitions,
        "boss_death_confirmed": state["boss_death"],
        "victory": terminal == "level_victory",
        "failed": terminal == "level_failed",
        "terminated": terminal is not None,
        "event_summary": dict(sorted(event_summary.items())),
        "ignored_events": ignored_events,
        "rejected_events": rejected_events,
        "errors": errors,
        "events_processed": events_processed,
        "sequence_gaps": state["sequence_gaps"],
    }


def replay_document(document) -> dict:
    """回放一份已解析的 trace 文档（`load_trace` 的产物）。"""
    if not isinstance(document, dict):
        return _fatal_input("invalid_document", "trace root must be a JSON object")
    events = document.get("events")
    if not isinstance(events, list):
        return _fatal_input("invalid_document", "trace 'events' must be an array")
    return replay(events, run_id=str(document.get("run_id") or ""),
                  event_count=document.get("event_count"),
                  dropped_events=int(document.get("dropped_events") or 0),
                  document=document)


def _fatal_input(reason: str, message: str) -> dict:
    result = _result([{"sequence": None, "reason": reason, "message": message}],
                     [], [], [], [], [], Counter(), {
                         "started": False, "mode": None, "stage_count": 0,
                         "requires_boss_death": False, "boss_death": False,
                         "terminal": None, "current": None, "last_started": None,
                         "last_completed": None, "pending_expected": None,
                         "sequence_gaps": 0,
                         "wave_total": None, "wave_started_count": 0,
                         "wave_current": None, "wave_cleared_count": 0,
                         "exit_unlocked": False,
                     }, "", 0)
    return result


def format_report(result: dict, path: str = "") -> str:
    lines = ["Orchestration Trace Replay"]
    if path:
        lines.append("  File: %s" % path)
    lines.append("  Run: %s" % (result.get("run_id") or "<none>"))
    lines.append("  Events: %d (schema %d)" % (result.get("events_processed", 0),
                                               result.get("schema_version", 0)))
    lines.append("  Mode: %s" % (result.get("mode") or "<unknown>"))
    lines.append("  Final state: %s" % result.get("final_state"))
    started = ", ".join("%s@%s" % (stage["stage_id"], stage["stage_index"])
                        for stage in result.get("started_stages") or []) or "<none>"
    completed = ", ".join("%s@%s" % (stage["stage_id"], stage["stage_index"])
                          for stage in result.get("completed_stages") or []) or "<none>"
    lines.append("  Stages started: %s" % started)
    lines.append("  Stages completed: %s" % completed)
    lines.append("  Boss death confirmed: %s" % ("yes" if result.get("boss_death_confirmed")
                                                 else "no"))
    ignored = result.get("ignored_events") or []
    lines.append("  Duplicate notifications ignored: %d" % len(ignored))
    if result.get("errors"):
        lines.append("  Errors: %d" % len(result["errors"]))
        for error in result["errors"]:
            lines.append("    [sequence=%s] %s: %s"
                         % (error.get("sequence"), error.get("reason"),
                            error.get("message")))
    return "\n".join(lines)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Read and deterministically replay an exported orchestration trace.")
    parser.add_argument("trace", help="path to an exported orchestration trace JSON")
    parser.add_argument("--json", action="store_true", help="print the replay result as JSON")
    args = parser.parse_args(argv)

    try:
        document = load_trace(args.trace)
    except TraceInputError as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 2
    if document.get("schema_version") != SCHEMA_VERSION:
        print("FAIL: %s: unsupported schema_version %r (expected %d)"
              % (args.trace, document.get("schema_version"), SCHEMA_VERSION),
              file=sys.stderr)
        return 2

    result = replay_document(document)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_report(result, args.trace))
    if not result["ok"]:
        for error in result["errors"]:
            print("FAIL: [sequence=%s] %s: %s"
                  % (error.get("sequence"), error.get("reason"), error.get("message")),
                  file=sys.stderr)
        return 1
    if not args.json:
        print("PASS: orchestration trace is valid and replayable (final=%s)"
              % result["final_state"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
