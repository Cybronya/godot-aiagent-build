#!/usr/bin/env python3
"""Golden Trace Baselines（Phase 1.23）

把 Phase 1.22 导出的真实编排诊断 trace 变成**可审查、可版本控制、可自动比较**的
黄金基线，并给出结构化回归判定：

    python .ai/tools/validator/trace_baselines.py <trace.json> \
        --scenario multi_stage_boss [--baseline <baseline.json>] [--json]

数据流：Real Godot E2E → Runtime Trace → Schema Validation → Trace Replay →
Golden Baseline Diff → Regression Verdict。

边界（必须保持）：
  - 本模块**只读**：不调用 Godot、不写基线、不生成候选（候选由
    `.ai/tools/e2e/approve_trace_baselines.py` 显式生成与批准）。
  - 比较失败**绝不**改写基线；基线只能由显式批准流程替换。
  - 不排序事件、不比较“事件数量”或“最终状态”了事：逐事件按顺序对齐比较。
  - 动态字段只按**显式策略**归一化（默认仅 `run_id` / `timestamp_ms`），
    其余字段（含 `data`）默认严格比较。
  - “比较通过”只表示事件流与已批准基线一致，不代表重新执行了游戏。

退出码（Phase 1.29 显式锁定；测试 U91 / U92 守护）：
  0 = PASS
  1 = REGRESSION / INCOMPLETE / INVALID_TRACE
      包括「trace 文件不存在 / 不可读 / 非法 JSON」：本入口把它归为 trace 不可用
      （INVALID_TRACE，不会当成 PASS）。只读回放 CLI（trace_replay.py）对同一条件
      返回**输入错误 2**；两者均非 0，差异已文档化并锁定，不得静默改变。
  2 = BASELINE_MISSING / INVALID_BASELINE（基线缺失、不可读、非法 JSON 或不符合契约）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

_VALIDATOR_DIR = Path(__file__).resolve().parent
if str(_VALIDATOR_DIR) not in sys.path:                     # 允许 from .ai/tools 外部调用
    sys.path.insert(0, str(_VALIDATOR_DIR))

import trace_replay                                          # noqa: E402

PROJECT_ROOT = _VALIDATOR_DIR.parent.parent.parent
BASELINE_DIR = _VALIDATOR_DIR / "baselines"

BASELINE_DOCUMENT = "orchestration_trace_baseline"
TRACE_DOCUMENT = trace_replay.DOCUMENT
TRACE_SCHEMA_VERSION = trace_replay.SCHEMA_VERSION
BASELINE_SCHEMA_VERSION = 1
POLICY_VERSION = 1

STATUS_PASS = "PASS"
STATUS_REGRESSION = "REGRESSION"
STATUS_INCOMPLETE = "INCOMPLETE"
STATUS_INVALID_TRACE = "INVALID_TRACE"
STATUS_INVALID_BASELINE = "INVALID_BASELINE"
STATUS_BASELINE_MISSING = "BASELINE_MISSING"

EXIT_CODES = {
    STATUS_PASS: 0,
    STATUS_REGRESSION: 1,
    STATUS_INCOMPLETE: 1,
    STATUS_INVALID_TRACE: 1,
    STATUS_BASELINE_MISSING: 2,
    STATUS_INVALID_BASELINE: 2,
}

# 事件级别字段（严格比较；仅策略显式列出的字段可豁免）
KEY_FIELDS = ("event_type", "stage_id", "stage_index", "reason",
              "entity_id", "instance_name")
STRICT_FIELDS = KEY_FIELDS + ("source",)
# 允许被策略声明为动态的字段：只有运行标识与运行时相对时间
ALLOWED_DYNAMIC_FIELDS = ("run_id", "timestamp_ms")
REQUIRED_EVENT_FIELDS = trace_replay.REQUIRED_FIELDS
TERMINAL_TYPES = trace_replay.TERMINAL_TYPES
INCOMPLETE_REASONS = ("trace_incomplete", "truncated_trace")

DEFAULT_POLICY = {
    "version": POLICY_VERSION,
    "ignored_event_fields": ["run_id", "timestamp_ms"],
    "data": {
        "mode": "strict",
        "ignored_fields": [],
        "numeric_tolerance": 1e-9,
    },
}

SUGGESTIONS = {
    "EVENT_MISSING": "该事件在本次运行中缺失：若属于有意的编排变更，请走候选生成 + 人工批准流程；否则修复产生该事件的边界。",
    "EVENT_EXTRA": "出现基线中不存在的新事件：确认是否为未批准的编排行为变化，批准前不要放行。",
    "EVENT_ORDER_CHANGED": "事件顺序与基线不一致（同一事件出现在不同位置）：检查阶段推进 / 结算顺序是否被改变。",
    "EVENT_TYPE_CHANGED": "事件类型变化：检查对应状态机边界是否被改写或新增了旁路触发。",
    "STAGE_ID_CHANGED": "阶段 ID 变化：检查配置 / 阶段规划是否改了身份，或运行时解析到了别的阶段。",
    "STAGE_INDEX_CHANGED": "阶段索引变化：检查阶段推进顺序是否被提前 / 跳过。",
    "REASON_CHANGED": "稳定 reason 代码变化：reason 是契约的一部分，不能在未批准的情况下改变。",
    "IDENTITY_CHANGED": "实体身份 / 宿主实例名变化：检查配置绑定的实体或实例解析结果。",
    "FIELD_CHANGED": "字段值与基线不一致：确认是否属于显式声明过的动态字段，否则视为回归。",
    "DATA_FIELD_CHANGED": "事件 data 字段变化：data 默认严格比较，行为变化需要显式策略或新基线。",
    "BOSS_DEATH_COUNT_CHANGED": "Boss 死亡确认次数变化：确认事件缺失或重复结算；一次运行必须恰好确认一次。",
    "TERMINAL_EVENT_CHANGED": "终结事件与基线不一致：检查胜利 / 失败判定是否被改变。",
    "TERMINAL_EVENT_EXTRA": "出现了多个或终结后的事件：终结只允许发生一次，之后只允许 duplicate_event_ignored。",
    "FINAL_STATE_CHANGED": "最终状态与基线不符：检查阶段链是否完整、终结原因是否正确。",
    "TRACE_INVALID": "trace 未通过格式 / 回放校验：先修 trace 契约，不要把它当作回归差异。",
    "TRACE_INCOMPLETE": "trace 被标记为不完整（记录器溢出或事件数不符）：不能用于回归判定。",
    "TRACE_SCHEMA_MISMATCH": "trace schema 版本与基线不一致：迁移或重新批准基线，不得静默接受。",
    "BASELINE_INVALID": "基线文件不符合契约：修复基线字段（不允许放宽比较规则来掩盖差异）。",
}


class BaselineError(ValueError):
    """基线文件不可读 / 不符合契约（比较结果 INVALID_BASELINE）。"""


def default_policy() -> dict:
    return json.loads(json.dumps(DEFAULT_POLICY))


def _freeze(value) -> str:
    """把 JSON 值规范化为可比较 / 可哈希的字符串。"""
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def file_sha256(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ============================ 比较策略 ============================


def validate_policy(policy) -> list:
    """校验比较策略；未知字段 / 非法配置一律拒绝（不静默忽略）。"""
    errors: list = []
    if not isinstance(policy, dict):
        return ["comparison_policy must be a JSON object"]
    allowed_keys = {"version", "ignored_event_fields", "data"}
    for key in sorted(set(policy) - allowed_keys):
        errors.append("comparison_policy contains unknown field %r" % key)
    if policy.get("version") != POLICY_VERSION:
        errors.append("comparison_policy.version must be %d (got %r)"
                      % (POLICY_VERSION, policy.get("version")))
    ignored = policy.get("ignored_event_fields", [])
    if not isinstance(ignored, list) or any(not isinstance(item, str) for item in ignored):
        errors.append("comparison_policy.ignored_event_fields must be a list of strings")
        ignored = []
    for field in ignored:
        if field not in ALLOWED_DYNAMIC_FIELDS:
            errors.append("comparison_policy.ignored_event_fields may not ignore %r "
                          "(allowed: %s)" % (field, ", ".join(ALLOWED_DYNAMIC_FIELDS)))
    data_policy = policy.get("data", {})
    if not isinstance(data_policy, dict):
        errors.append("comparison_policy.data must be a JSON object")
        return errors
    for key in sorted(set(data_policy) - {"mode", "ignored_fields", "numeric_tolerance"}):
        errors.append("comparison_policy.data contains unknown field %r" % key)
    if data_policy.get("mode", "strict") not in ("strict", "strict_with_ignored_keys"):
        errors.append("comparison_policy.data.mode must be 'strict' or "
                      "'strict_with_ignored_keys' (got %r)" % data_policy.get("mode"))
    data_ignored = data_policy.get("ignored_fields", [])
    if not isinstance(data_ignored, list) or any(not isinstance(item, str) for item in data_ignored):
        errors.append("comparison_policy.data.ignored_fields must be a list of strings")
    tolerance = data_policy.get("numeric_tolerance", 0.0)
    if not _is_number(tolerance) or float(tolerance) < 0.0:
        errors.append("comparison_policy.data.numeric_tolerance must be a non-negative number")
    return errors


def normalize_policy(policy=None) -> dict:
    merged = default_policy()
    if policy is None:
        return merged
    if isinstance(policy, dict):
        for key, value in policy.items():
            if key == "data" and isinstance(value, dict):
                merged["data"].update(value)
            else:
                merged[key] = value
    return merged


# ============================ 偏差记录 ============================


def _diff(category: str, sequence, path: str, expected, actual, detail: str = "") -> dict:
    return {
        "category": category,
        "sequence": sequence,
        "field_path": path,
        "expected": expected,
        "actual": actual,
        "detail": detail,
        "suggestion": SUGGESTIONS.get(category, "确认该差异是否为未批准的编排行为变化。"),
    }


# ============================ Trace 校验 ============================


def validate_trace_shape(document) -> list:
    """结构 / 序号 / 时间戳校验；返回 [{reason, sequence, message}]。"""
    errors: list = []

    def bad(reason: str, sequence, message: str) -> None:
        errors.append({"reason": reason, "sequence": sequence, "message": message})

    if not isinstance(document, dict):
        bad("invalid_document", None, "trace root must be a JSON object")
        return errors
    if document.get("document") != TRACE_DOCUMENT:
        bad("invalid_document", None, "trace document must be %r (got %r)"
            % (TRACE_DOCUMENT, document.get("document")))
    if document.get("schema_version") != TRACE_SCHEMA_VERSION:
        bad("unsupported_schema_version", None,
            "unsupported trace schema_version %r (expected %d)"
            % (document.get("schema_version"), TRACE_SCHEMA_VERSION))
    run_id = document.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        bad("invalid_document", None, "trace run_id must be a non-empty string")
    events = document.get("events")
    if not isinstance(events, list):
        bad("invalid_document", None, "trace 'events' must be an array")
        return errors
    event_count = document.get("event_count")
    if not _is_int(event_count):
        bad("invalid_document", None, "trace 'event_count' must be an integer")
    elif event_count != len(events):
        bad("truncated_trace", None, "event_count=%d but %d events present"
            % (event_count, len(events)))
    dropped = document.get("dropped_events", 0)
    if not _is_int(dropped) or dropped < 0:
        bad("invalid_document", None, "trace 'dropped_events' must be a non-negative integer")
    elif dropped > 0:
        bad("trace_incomplete", None,
            "recorder dropped %d event(s) (RECORDER_MAX_EVENTS overflow)" % dropped)

    previous_timestamp = -1
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            bad("invalid_event", index, "event must be a JSON object")
            continue
        missing = [field for field in REQUIRED_EVENT_FIELDS if field not in event]
        if missing:
            bad("invalid_event", index, "event is missing required field(s): %s"
                % ", ".join(missing))
            continue
        if event.get("schema_version") != TRACE_SCHEMA_VERSION:
            bad("unsupported_schema_version", index,
                "event schema_version %r != %d"
                % (event.get("schema_version"), TRACE_SCHEMA_VERSION))
        if isinstance(run_id, str) and event.get("run_id") != run_id:
            bad("run_id_mismatch", index, "event run_id %r != document run_id %r"
                % (event.get("run_id"), run_id))
        if not _is_int(event.get("sequence")) or event.get("sequence") != index:
            bad("sequence_not_contiguous", index,
                "sequence must be %d (got %r)" % (index, event.get("sequence")))
        event_type = event.get("event_type")
        if event_type not in trace_replay.KNOWN_TYPES:
            bad("unknown_event_type", index, "unknown event_type %r" % (event_type,))
        timestamp = event.get("timestamp_ms")
        if not _is_int(timestamp) or timestamp < 0:
            bad("invalid_timestamp", index, "timestamp_ms must be a non-negative integer")
        else:
            if timestamp < previous_timestamp:
                bad("timestamp_regression", index,
                    "timestamp_ms %d went backwards from %d" % (timestamp, previous_timestamp))
            previous_timestamp = max(previous_timestamp, timestamp)
        if not isinstance(event.get("data"), dict):
            bad("invalid_event", index, "event data must be a JSON object")
    return errors


def _incomplete(errors) -> bool:
    return any(error.get("reason") in INCOMPLETE_REASONS for error in errors)


def _only_incomplete(errors) -> bool:
    return bool(errors) and all(error.get("reason") in INCOMPLETE_REASONS for error in errors)


def validate_trace(document) -> tuple:
    """返回 (status, errors, replay_result)。status 为 None 表示 trace 合法。"""
    shape_errors = validate_trace_shape(document)
    hard_errors = [error for error in shape_errors
                   if error.get("reason") not in INCOMPLETE_REASONS]
    if hard_errors:
        return STATUS_INVALID_TRACE, shape_errors, None
    replay_result = trace_replay.replay_document(document)
    replay_errors = replay_result.get("errors") or []
    hard_replay = [error for error in replay_errors
                   if error.get("reason") not in INCOMPLETE_REASONS]
    if hard_replay:
        return STATUS_INVALID_TRACE, shape_errors + replay_errors, replay_result
    if shape_errors or replay_errors:
        return STATUS_INCOMPLETE, shape_errors + replay_errors, replay_result
    return None, [], replay_result


# ============================ 基线契约 ============================


def baseline_path_for(scenario_id: str, baseline_dir=None) -> Path:
    base = Path(baseline_dir) if baseline_dir else BASELINE_DIR
    return base / ("%s.json" % scenario_id)


def validate_baseline(baseline) -> list:
    """校验黄金基线文档（结构 + 事件回放语义）；返回错误字符串列表（空 = 合法）。

    Phase 1.28：结构合法但回放不合法（跨模式事件 / 模式化终结原因 / 重复终结……）的
    事件流不是合法基线——比较器必须先拒基线，而不是把问题归给真实 trace。
    """
    if not isinstance(baseline, dict):
        return ["baseline root must be a JSON object"]
    errors: list = []
    if baseline.get("document") != BASELINE_DOCUMENT:
        errors.append("baseline document must be %r (got %r)"
                      % (BASELINE_DOCUMENT, baseline.get("document")))
    if baseline.get("baseline_schema_version") != BASELINE_SCHEMA_VERSION:
        errors.append("baseline_schema_version must be %d (got %r)"
                      % (BASELINE_SCHEMA_VERSION, baseline.get("baseline_schema_version")))
    if baseline.get("trace_schema_version") != TRACE_SCHEMA_VERSION:
        errors.append("trace_schema_version must be %d (got %r)"
                      % (TRACE_SCHEMA_VERSION, baseline.get("trace_schema_version")))
    version = baseline.get("baseline_version")
    if not _is_int(version) or version < 1:
        errors.append("baseline_version must be an integer >= 1")
    for field in ("scenario_id", "scenario_description", "approved_behavior_version"):
        value = baseline.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append("%s must be a non-empty string" % field)
    approval = baseline.get("approval")
    if not isinstance(approval, dict):
        errors.append("approval must be a JSON object describing the approval record")
    else:
        if approval.get("status") != "approved":
            errors.append("approval.status must be 'approved' (got %r)"
                          % (approval.get("status"),))
        if not isinstance(approval.get("approver"), str) or not approval.get("approver").strip():
            errors.append("approval.approver must be a non-empty string")
        if not isinstance(approval.get("approved_at"), str) or not approval.get("approved_at").strip():
            errors.append("approval.approved_at must be a non-empty string")
    errors.extend(validate_policy(normalize_policy(baseline.get("comparison_policy"))))
    expected = baseline.get("expected_final_state")
    if not isinstance(expected, dict) or not isinstance(expected.get("final_state"), str):
        errors.append("expected_final_state.final_state must be a string")
    events = baseline.get("events")
    if not isinstance(events, list) or not events:
        errors.append("baseline events must be a non-empty array")
        return errors
    # 基线内的事件必须自身满足 trace 事件契约（序号 +1 / 必备字段 / 时间戳非递减）。
    previous_timestamp = -1
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            errors.append("events[%d] must be a JSON object" % index)
            continue
        missing = [field for field in REQUIRED_EVENT_FIELDS if field not in event]
        if missing:
            errors.append("events[%d] is missing required field(s): %s"
                          % (index, ", ".join(missing)))
            continue
        if event.get("sequence") != index:
            errors.append("events[%d].sequence must be %d (got %r)"
                          % (index, index, event.get("sequence")))
        if event.get("event_type") not in trace_replay.KNOWN_TYPES:
            errors.append("events[%d].event_type %r is not a known event type"
                          % (index, event.get("event_type")))
        timestamp = event.get("timestamp_ms")
        if not _is_int(timestamp) or timestamp < 0:
            errors.append("events[%d].timestamp_ms must be a non-negative integer" % index)
        else:
            if timestamp < previous_timestamp:
                errors.append("events[%d].timestamp_ms went backwards" % index)
            previous_timestamp = max(previous_timestamp, timestamp)
        if not isinstance(event.get("data"), dict):
            errors.append("events[%d].data must be a JSON object" % index)
    # Phase 1.28：结构合法的基线事件也必须能通过回放（公共语义一致性）。否则一份被手改的
    # 基线会被当作合法基线参与比较，把「基线本身不可能发生」错报成 trace 的回归。
    if not errors:
        replay_result = trace_replay.replay(events)
        if not replay_result.get("ok"):
            for error in replay_result.get("errors") or []:
                errors.append("events must replay: [sequence=%s] %s: %s"
                              % (error.get("sequence"), error.get("reason"),
                                 error.get("message")))
    return errors


def load_baseline(path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(str(path))
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BaselineError("cannot read baseline %s: %s" % (path, exc))
    except ValueError as exc:
        raise BaselineError("%s: invalid JSON: %s" % (path, exc))
    errors = validate_baseline(document)
    if errors:
        raise BaselineError("%s: %s" % (path, "; ".join(errors)))
    return document


def build_baseline(trace_document, *, scenario_id: str, scenario_description: str,
                   approved_behavior_version: str, approval: dict, source: dict,
                   coverage=None, baseline_version: int = 1,
                   policy=None) -> dict:
    """用**真实运行**的 trace 构造基线文档；trace 非法 / 不完整一律拒绝。"""
    status, errors, replay_result = validate_trace(trace_document)
    if status is not None:
        raise BaselineError("cannot build a baseline from this trace: %s (%s)"
                            % (status, json.dumps(errors[:3], ensure_ascii=False)))
    events = trace_document["events"]
    expected_final_state = {
        "final_state": replay_result["final_state"],
        "boss_death_confirmed": replay_result["boss_death_confirmed"],
        "stage_history": ["%s@%s" % (stage["stage_id"], stage["stage_index"])
                          for stage in replay_result["completed_stages"]],
        "terminal_event": events[-1]["event_type"],
        "event_count": len(events),
    }
    return {
        "document": BASELINE_DOCUMENT,
        "baseline_schema_version": BASELINE_SCHEMA_VERSION,
        "baseline_version": baseline_version,
        "trace_schema_version": trace_document.get("schema_version"),
        "scenario_id": scenario_id,
        "scenario_description": scenario_description,
        "coverage": list(coverage or []),
        "approved_behavior_version": approved_behavior_version,
        "source": dict(source or {}),
        "approval": dict(approval or {}),
        "comparison_policy": normalize_policy(policy),
        "expected_final_state": expected_final_state,
        "events": events,
    }


# ============================ 比较 ============================


def _compare_fields(expected_event: dict, actual_event: dict, index: int,
                    ignored: set, data_policy: dict, differences: list) -> bool:
    """比较一对已对齐事件；返回是否完全一致。"""
    matched = True
    for field in STRICT_FIELDS + ("run_id", "timestamp_ms"):
        if field in ignored:
            continue
        expected_value = expected_event.get(field)
        actual_value = actual_event.get(field)
        if _freeze(expected_value) == _freeze(actual_value):
            continue
        matched = False
        category = {
            "event_type": "EVENT_TYPE_CHANGED",
            "stage_id": "STAGE_ID_CHANGED",
            "stage_index": "STAGE_INDEX_CHANGED",
            "reason": "REASON_CHANGED",
            "entity_id": "IDENTITY_CHANGED",
            "instance_name": "IDENTITY_CHANGED",
        }.get(field, "FIELD_CHANGED")
        differences.append(_diff(category, expected_event.get("sequence"),
                                 "events[%d].%s" % (index, field),
                                 expected_value, actual_value))
    expected_extra = sorted(set(expected_event) - set(REQUIRED_EVENT_FIELDS) - set(STRICT_FIELDS))
    actual_extra = sorted(set(actual_event) - set(REQUIRED_EVENT_FIELDS) - set(STRICT_FIELDS))
    if expected_extra != actual_extra:
        matched = False
        differences.append(_diff("FIELD_CHANGED", expected_event.get("sequence"),
                                 "events[%d].<fields>" % index,
                                 expected_extra, actual_extra,
                                 "事件字段集合不一致"))
    tolerance = float(data_policy.get("numeric_tolerance", 0.0))
    data_ignored = set(data_policy.get("ignored_fields") or [])
    expected_data = expected_event.get("data") or {}
    actual_data = actual_event.get("data") or {}
    for key in sorted(set(expected_data) | set(actual_data)):
        if key in data_ignored:
            continue
        if key not in expected_data:
            matched = False
            differences.append(_diff("DATA_FIELD_CHANGED", expected_event.get("sequence"),
                                     "events[%d].data.%s" % (index, key),
                                     "<absent>", actual_data.get(key)))
            continue
        if key not in actual_data:
            matched = False
            differences.append(_diff("DATA_FIELD_CHANGED", expected_event.get("sequence"),
                                     "events[%d].data.%s" % (index, key),
                                     expected_data.get(key), "<absent>"))
            continue
        expected_value = expected_data[key]
        actual_value = actual_data[key]
        if _is_number(expected_value) and _is_number(actual_value):
            if abs(float(expected_value) - float(actual_value)) <= tolerance:
                continue
        elif _freeze(expected_value) == _freeze(actual_value):
            continue
        matched = False
        differences.append(_diff("DATA_FIELD_CHANGED", expected_event.get("sequence"),
                                 "events[%d].data.%s" % (index, key),
                                 expected_value, actual_value))
    return matched


def _align(expected_events: list, actual_events: list) -> list:
    """按事件身份键做 LCS 对齐（不排序，只用于定位缺失 / 新增 / 换位）。"""
    def key_of(event):
        return tuple(_freeze(event.get(field)) for field in KEY_FIELDS) + \
            (_freeze(event.get("source")),)

    return list(SequenceMatcher(a=[key_of(event) for event in expected_events],
                                b=[key_of(event) for event in actual_events],
                                autojunk=False).get_opcodes())


def _diff_events(baseline: dict, trace: dict, ignored: set,
                 data_policy: dict) -> tuple:
    expected_events = baseline["events"]
    actual_events = trace["events"]
    differences: list = []
    matched = 0

    expected_counter = Counter(_freeze({field: event.get(field) for field in KEY_FIELDS})
                               for event in expected_events)
    actual_counter = Counter(_freeze({field: event.get(field) for field in KEY_FIELDS})
                             for event in actual_events)
    surplus_actual = actual_counter - expected_counter
    surplus_expected = expected_counter - actual_counter

    def identity(event) -> str:
        return _freeze({field: event.get(field) for field in KEY_FIELDS})

    def key_of(event) -> str:
        return _freeze({field: event.get(field) for field in KEY_FIELDS})

    for tag, i1, i2, j1, j2 in _align(expected_events, actual_events):
        if tag == "equal":
            for offset in range(i2 - i1):
                if _compare_fields(expected_events[i1 + offset], actual_events[j1 + offset],
                                   i1 + offset, ignored, data_policy, differences):
                    matched += 1
            continue
        if tag == "replace":
            expected_keys = [key_of(event) for event in expected_events[i1:i2]]
            actual_keys = [key_of(event) for event in actual_events[j1:j2]]
            if Counter(expected_keys) == Counter(actual_keys):
                # 纯换位：事件集合相同、顺序不同（不排序，如实报告顺序变化）。
                for index in range(i1, i2):
                    differences.append(_diff("EVENT_ORDER_CHANGED",
                                             expected_events[index].get("sequence"),
                                             "events[%d].event_type" % index,
                                             expected_events[index].get("event_type"),
                                             "<moved>",
                                             "同一事件出现在不同位置（阶段 / 结算顺序变化）"))
                continue
            if (i2 - i1) == (j2 - j1):
                # 同位替换：逐字段比较，给出 REASON_CHANGED / STAGE_* 等具体类别。
                for offset in range(i2 - i1):
                    if _compare_fields(expected_events[i1 + offset],
                                       actual_events[j1 + offset], i1 + offset,
                                       ignored, data_policy, differences):
                        matched += 1
                continue
        for index in range(i1, i2):
            event = expected_events[index]
            if surplus_actual[identity(event)] > 0:
                surplus_actual[identity(event)] -= 1
                differences.append(_diff("EVENT_ORDER_CHANGED", event.get("sequence"),
                                         "events[%d].event_type" % index,
                                         event.get("event_type"), "<moved>",
                                         "同一事件出现在不同位置（阶段 / 结算顺序变化）"))
            else:
                differences.append(_diff("EVENT_MISSING", event.get("sequence"),
                                         "events[%d].event_type" % index,
                                         event.get("event_type"), "<absent>"))
        for index in range(j1, j2):
            event = actual_events[index]
            if surplus_expected[identity(event)] > 0:
                surplus_expected[identity(event)] -= 1
                differences.append(_diff("EVENT_ORDER_CHANGED", event.get("sequence"),
                                         "events[%d].event_type" % index,
                                         "<moved>", event.get("event_type"),
                                         "同一事件出现在不同位置（阶段 / 结算顺序变化）"))
            else:
                differences.append(_diff("EVENT_EXTRA", event.get("sequence"),
                                         "events[%d].event_type" % index,
                                         "<absent>", event.get("event_type")))
    return matched, differences


def _diff_contract_state(baseline: dict, trace: dict, replay_result: dict,
                         differences: list) -> None:
    expected_events = baseline["events"]
    actual_events = trace["events"]
    expected_deaths = sum(1 for event in expected_events
                          if event.get("event_type") == "boss_death_confirmed")
    actual_deaths = sum(1 for event in actual_events
                        if event.get("event_type") == "boss_death_confirmed")
    if expected_deaths != actual_deaths:
        differences.append(_diff("BOSS_DEATH_COUNT_CHANGED", None,
                                 "events[].boss_death_confirmed",
                                 expected_deaths, actual_deaths,
                                 "Boss 死亡确认次数变化（缺失或重复结算）"))

    expected_terminal = [event.get("event_type") for event in expected_events
                         if event.get("event_type") in TERMINAL_TYPES]
    actual_terminal = [event.get("event_type") for event in actual_events
                       if event.get("event_type") in TERMINAL_TYPES]
    if expected_terminal != actual_terminal:
        category = ("TERMINAL_EVENT_EXTRA" if len(actual_terminal) > 1
                    or len(actual_terminal) > len(expected_terminal)
                    else "TERMINAL_EVENT_CHANGED")
        differences.append(_diff(category, None, "events[].terminal",
                                 expected_terminal, actual_terminal))
    last_type = actual_events[-1].get("event_type") if actual_events else None
    if actual_events and last_type not in TERMINAL_TYPES \
            and last_type != "duplicate_event_ignored" \
            and any(event.get("event_type") in TERMINAL_TYPES for event in actual_events):
        differences.append(_diff("TERMINAL_EVENT_EXTRA", actual_events[-1].get("sequence"),
                                 "events[%d].event_type" % (len(actual_events) - 1),
                                 "duplicate_event_ignored (after terminal)",
                                 last_type,
                                 "终结之后出现了非 duplicate_event_ignored 事件"))

    expected_final = baseline.get("expected_final_state") or {}
    actual_final = {
        "final_state": replay_result.get("final_state"),
        "boss_death_confirmed": replay_result.get("boss_death_confirmed"),
        "stage_history": ["%s@%s" % (stage["stage_id"], stage["stage_index"])
                          for stage in replay_result.get("completed_stages") or []],
    }
    for field in ("final_state", "boss_death_confirmed", "stage_history"):
        if field not in expected_final:
            continue
        if _freeze(expected_final[field]) == _freeze(actual_final[field]):
            continue
        differences.append(_diff("FINAL_STATE_CHANGED", None, "expected_final_state.%s" % field,
                                 expected_final[field], actual_final[field]))


def compare(baseline: dict, trace, *, baseline_path: str = "") -> dict:
    """比较已批准的基线与本次真实 trace；返回结构化结果（不写任何文件）。"""
    policy = normalize_policy(baseline.get("comparison_policy") if isinstance(baseline, dict)
                              else None)
    result = {
        "status": STATUS_PASS,
        "scenario_id": baseline.get("scenario_id") if isinstance(baseline, dict) else None,
        "baseline_path": baseline_path,
        "baseline_version": baseline.get("baseline_version") if isinstance(baseline, dict) else None,
        "baseline_schema_version": (baseline.get("baseline_schema_version")
                                    if isinstance(baseline, dict) else None),
        "approved_behavior_version": (baseline.get("approved_behavior_version")
                                      if isinstance(baseline, dict) else None),
        "expected_trace_schema_version": (baseline.get("trace_schema_version")
                                          if isinstance(baseline, dict) else None),
        "actual_trace_schema_version": (trace.get("schema_version")
                                        if isinstance(trace, dict) else None),
        "trace_run_id": trace.get("run_id") if isinstance(trace, dict) else None,
        "expected_event_count": len(baseline.get("events") or []) if isinstance(baseline, dict) else 0,
        "actual_event_count": len(trace.get("events") or []) if isinstance(trace, dict) else 0,
        "matched_event_count": 0,
        "differences": [],
        "first_difference": None,
        "summary": "",
        "policy": policy,
        "final_state": None,
    }

    baseline_errors = validate_baseline(baseline)
    if baseline_errors:
        result["status"] = STATUS_INVALID_BASELINE
        result["differences"] = [_diff("BASELINE_INVALID", None, "<baseline>", None, error)
                                 for error in baseline_errors]
        return _finalize(result)

    status, trace_errors, replay_result = validate_trace(trace)
    if result["actual_trace_schema_version"] != result["expected_trace_schema_version"]:
        result["differences"].append(
            _diff("TRACE_SCHEMA_MISMATCH", None, "schema_version",
                  result["expected_trace_schema_version"],
                  result["actual_trace_schema_version"]))
        if status is None:
            status = STATUS_INVALID_TRACE
    if status is not None:
        result["status"] = status
        category = "TRACE_INCOMPLETE" if status == STATUS_INCOMPLETE else "TRACE_INVALID"
        for error in trace_errors:
            result["differences"].append(
                _diff(category, error.get("sequence"), "errors[%s]" % error.get("reason"),
                      None, error.get("message")))
        return _finalize(result)

    result["final_state"] = replay_result.get("final_state")
    ignored = set(policy.get("ignored_event_fields") or [])
    matched, differences = _diff_events(baseline, trace, ignored, policy.get("data") or {})
    result["matched_event_count"] = matched
    _diff_contract_state(baseline, trace, replay_result, differences)
    result["differences"] = differences
    result["status"] = STATUS_PASS if not differences else STATUS_REGRESSION
    return _finalize(result)


def _finalize(result: dict) -> dict:
    differences = result.get("differences") or []
    result["first_difference"] = differences[0] if differences else None
    result["exit_code"] = EXIT_CODES[result["status"]]
    status = result["status"]
    if status == STATUS_PASS:
        result["summary"] = ("PASS: %s matches the approved baseline (v%s) event by event "
                            "(%d/%d events, schema %s)"
                            % (result.get("scenario_id"), result.get("baseline_version"),
                               result["matched_event_count"], result["expected_event_count"],
                               result.get("actual_trace_schema_version")))
    elif status == STATUS_BASELINE_MISSING:
        result["summary"] = ("BASELINE_MISSING: no approved baseline for scenario %r "
                            "(run approve_trace_baselines.py candidate, review, then approve)"
                            % result.get("scenario_id"))
    elif status == STATUS_INVALID_BASELINE:
        result["summary"] = "INVALID_BASELINE: %d contract error(s)" % len(differences)
    elif status == STATUS_INCOMPLETE:
        result["summary"] = ("INCOMPLETE: the trace cannot be used for regression judgement "
                            "(%d error(s), first: %s)"
                            % (len(differences),
                               differences[0].get("actual") if differences else "-"))
    elif status == STATUS_INVALID_TRACE:
        result["summary"] = ("INVALID_TRACE: the trace violates the orchestration trace contract "
                            "(%d error(s), first: %s)"
                            % (len(differences),
                               differences[0].get("actual") if differences else "-"))
    else:
        first = result["first_difference"] or {}
        result["summary"] = ("REGRESSION: %d difference(s); first at %s (expected %s, got %s)"
                            % (len(differences), first.get("field_path"),
                               first.get("expected"), first.get("actual")))
    return result


def compare_files(trace_path, baseline_path, *, scenario_id: str = "") -> dict:
    """按文件比较；基线缺失 / 非法返回对应状态而不是抛异常。

    Phase 1.29：输入类错误的映射被显式锁定——trace 不可读 → INVALID_TRACE（exit 1），
    基线缺失 → BASELINE_MISSING、基线不可读 / 非法 → INVALID_BASELINE（均 exit 2）。
    """
    trace_path = Path(trace_path)
    baseline_path = Path(baseline_path)
    scenario = scenario_id or baseline_path.stem
    if not baseline_path.is_file():
        result = {
            "status": STATUS_BASELINE_MISSING,
            "scenario_id": scenario,
            "baseline_path": str(baseline_path),
            "baseline_version": None,
            "baseline_schema_version": None,
            "approved_behavior_version": None,
            "expected_trace_schema_version": None,
            "actual_trace_schema_version": None,
            "trace_run_id": None,
            "expected_event_count": 0,
            "actual_event_count": 0,
            "matched_event_count": 0,
            "differences": [],
            "first_difference": None,
            "summary": "",
            "policy": default_policy(),
            "final_state": None,
        }
        return _finalize(result)
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        result = {
            "status": STATUS_INVALID_BASELINE, "scenario_id": scenario,
            "baseline_path": str(baseline_path), "baseline_version": None,
            "baseline_schema_version": None, "approved_behavior_version": None,
            "expected_trace_schema_version": None, "actual_trace_schema_version": None,
            "trace_run_id": None, "expected_event_count": 0, "actual_event_count": 0,
            "matched_event_count": 0,
            "differences": [_diff("BASELINE_INVALID", None, "<baseline>", None,
                                  "invalid JSON: %s" % exc)],
            "first_difference": None, "summary": "", "policy": default_policy(),
            "final_state": None,
        }
        return _finalize(result)
    try:
        trace = trace_replay.load_trace(trace_path)
    except trace_replay.TraceInputError as exc:
        result = {
            "status": STATUS_INVALID_TRACE, "scenario_id": scenario,
            "baseline_path": str(baseline_path),
            "baseline_version": baseline.get("baseline_version"),
            "baseline_schema_version": baseline.get("baseline_schema_version"),
            "approved_behavior_version": baseline.get("approved_behavior_version"),
            "expected_trace_schema_version": baseline.get("trace_schema_version"),
            "actual_trace_schema_version": None, "trace_run_id": None,
            "expected_event_count": len(baseline.get("events") or []),
            "actual_event_count": 0, "matched_event_count": 0,
            "differences": [_diff("TRACE_INVALID", None, "<trace>", None, str(exc))],
            "first_difference": None, "summary": "", "policy": default_policy(),
            "final_state": None,
        }
        return _finalize(result)
    return compare(baseline, trace, baseline_path=str(baseline_path))


# ============================ 报告 / CLI ============================


def format_report(result: dict) -> str:
    lines = ["Golden Trace Baseline Comparison"]
    lines.append("  Scenario: %s" % result.get("scenario_id"))
    lines.append("  Status: %s (exit %d)" % (result["status"], result.get("exit_code", 0)))
    lines.append("  Baseline: %s (v%s, schema %s, behavior %s)"
                 % (result.get("baseline_path") or "<none>", result.get("baseline_version"),
                    result.get("baseline_schema_version"),
                    result.get("approved_behavior_version")))
    lines.append("  Trace schema: expected %s, actual %s"
                 % (result.get("expected_trace_schema_version"),
                    result.get("actual_trace_schema_version")))
    lines.append("  Events: expected %d, actual %d, matched %d, differences %d"
                 % (result.get("expected_event_count"), result.get("actual_event_count"),
                    result.get("matched_event_count"), len(result.get("differences") or [])))
    lines.append("  Summary: %s" % result.get("summary"))
    differences = result.get("differences") or []
    if differences:
        lines.append("  First difference: %s" % json.dumps(differences[0], ensure_ascii=False))
        for difference in differences[:20]:
            lines.append("    [%s] sequence=%s %s: expected %s, actual %s"
                         % (difference.get("category"), difference.get("sequence"),
                            difference.get("field_path"),
                            json.dumps(difference.get("expected"), ensure_ascii=False),
                            json.dumps(difference.get("actual"), ensure_ascii=False)))
        if len(differences) > 20:
            lines.append("    ... %d more difference(s)" % (len(differences) - 20))
    return "\n".join(lines)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Compare a real orchestration trace against an approved golden baseline.")
    parser.add_argument("trace", help="path to the exported orchestration trace JSON")
    parser.add_argument("--scenario", default="",
                        help="scenario id (resolves .ai/tools/validator/baselines/<id>.json)")
    parser.add_argument("--baseline", default="", help="explicit baseline path")
    parser.add_argument("--baseline-dir", default="", help="override the baseline directory")
    parser.add_argument("--json", action="store_true", help="print the structured result as JSON")
    args = parser.parse_args(argv)

    baseline_path = Path(args.baseline) if args.baseline else None
    if baseline_path is None:
        if not args.scenario:
            parser.error("either --baseline or --scenario is required")
        baseline_path = baseline_path_for(args.scenario, args.baseline_dir or None)

    result = compare_files(args.trace, baseline_path, scenario_id=args.scenario)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_report(result))
    if result["status"] != STATUS_PASS:
        print("FAIL: %s" % result["summary"], file=sys.stderr)
    return result.get("exit_code", 1)


if __name__ == "__main__":
    sys.exit(main())
