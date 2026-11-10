#!/usr/bin/env python3
"""Behavior Evidence validation stage (Phase 1.56).

把 Phase 1.40–1.54 产生的**真实执行**行为证据接到 Validator 上：

    Feature 实现 → 真实 Godot 动作执行 → 证据包（bundle JSON）→ 本模块独立复核

三条硬约束（不许退化成“信任 PASS 字段”）：

1. **不信任证据自报的 `status`**：本模块用 `template.yaml#behavior` 的契约参数
   与证据里的**观测值**（`observed` / `observed_args`）重算每条断言的成立性。
2. **等级不互相冒充**：证据包声明 `evidence_level: L4`；本模块只输出 L4 复核结论。
   L2 由 `check_instance_evidence` 负责，L5 需要缺陷注入证明，本阶段不代其声明。
3. **不确定就 INCOMPLETE**：观测缺失、观测值与契约不可比较、重放不足时返回
   `INCOMPLETE`，绝不因为“文件存在”或“自报 PASS”而给 PASS。
4. **`--feature` 是范围，不是黑名单**：只验证被请求的 Feature；同一证据包里其他
   已存在的 Feature 记录记为 `summary.skipped_features`（不连坐为失败）；指向不
   存在的 Feature 的证据仍然拒绝。

内容完整性：证据包带 `integrity.payload_sha256`，本模块用规范化 JSON 重新计算。
它能发现“生成后被改动”，**不能**证明来源可信（能同时改实现并重签的人仍可伪造），
该信任边界在报告与文档中显式记录。

用法（通常经由 Validator 调用）：

    python .ai/tools/validator/check_behavior_evidence.py --evidence-dir .ai/tmp/behavior_bundles
    python .ai/tools/validator/check_behavior_evidence.py --evidence-dir DIR --feature health
    python .ai/tools/validator/check_behavior_evidence.py --evidence-dir DIR --json report.json

退出码：0 = PASS，1 = FAIL，2 = INCOMPLETE，3 = ERROR。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
_DOTAI = os.path.dirname(_TOOLS)
PROJECT_ROOT = os.path.dirname(_DOTAI)
SCENE_COMPOSER = os.path.join(_TOOLS, "scene_composer")
for _path in (SCENE_COMPOSER, _TOOLS):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import behavior_protocol                                  # noqa: E402
import execution_artifacts as xval                        # noqa: E402
import feature_behavior_evidence as fbe                   # noqa: E402
import instance_evidence                                  # noqa: E402

DEFAULT_EVIDENCE_DIR = os.path.join(_DOTAI, "tmp", "behavior_bundles")
DEFAULT_MAX_AGE_HOURS = 24.0
SUPPORTED_LEVEL = fbe.EVIDENCE_LEVEL          # "L4"：本阶段唯一能独立复核的等级
SUPPORTED_SCHEMA = fbe.BUNDLE_SCHEMA
MAX_SUPPORTED_SCHEMA_VERSION = fbe.BUNDLE_SCHEMA_VERSION

STATUS_PASS = instance_evidence.STATUS_PASS
STATUS_FAIL = "FAIL"
STATUS_INCOMPLETE = "INCOMPLETE"
STATUS_ERROR = "ERROR"

MIN_REPLAYS = 2


# ---------------------------------------------------------------- 基础工具

def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _value_equal(observed, expected, tolerance: float) -> bool:
    if isinstance(expected, bool) or isinstance(observed, bool):
        return observed is expected
    if _is_number(expected) and _is_number(observed):
        return abs(float(observed) - float(expected)) <= float(tolerance or 0.0)
    if isinstance(expected, str) and isinstance(observed, str):
        return observed == expected
    if isinstance(expected, list) and isinstance(observed, list):
        if len(observed) < len(expected):
            return False
        return all(_value_equal(observed[index], expected[index], tolerance)
                   for index in range(len(expected)))
    return observed == expected


def _args_match(observed, expected) -> bool:
    if not isinstance(observed, list):
        return False
    if len(observed) < len(expected):
        return False
    return all(_value_equal(observed[index], expected[index], 0.0)
               for index in range(len(expected)))


def parse_timestamp(text):
    """ISO-8601（允许 Z 后缀）-> aware datetime；无法解析时返回 None。"""
    if not isinstance(text, str) or not text.strip():
        return None
    cleaned = text.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def check_result(status: str, reason: str = "", detail: str = "") -> dict:
    return {"status": status, "reason": reason, "detail": detail}


def merge_verdicts(recomputed: dict, cross: dict) -> dict:
    """契约复算结论 + 执行产物交叉验证结论 -> 单一结论。

    FAIL 优先（已确认的数据矛盾比“无法判定”更能定性），其次 INCOMPLETE；
    两者都 PASS 时才算通过，并把交叉验证的事实写进 detail。
    """
    artifacts = cross.get("artifacts") or []
    if recomputed.get("status") == STATUS_FAIL:
        return recomputed
    if cross.get("status") == STATUS_FAIL:
        return check_result(STATUS_FAIL, cross["reason"],
                            "execution artifacts: %s" % cross["detail"])
    if recomputed.get("status") == STATUS_INCOMPLETE:
        return recomputed
    if cross.get("status") == STATUS_INCOMPLETE:
        return check_result(STATUS_INCOMPLETE, cross["reason"],
                            "execution artifacts: %s" % cross["detail"])
    return check_result(STATUS_PASS, "verified",
                        "%s; cross-validated against %d execution artifact(s)"
                        % (recomputed.get("detail", ""), len(artifacts)))


# ---------------------------------------------------------------- 证据加载

def load_bundle(path: str) -> tuple:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            document = json.load(handle)
    except OSError as exc:
        return None, ["bundle unreadable: %s" % exc]
    except ValueError as exc:
        return None, ["bundle is not valid JSON: %s" % exc]
    if not isinstance(document, dict):
        return None, ["bundle must be a JSON object"]
    errors = []
    if document.get("schema") != SUPPORTED_SCHEMA:
        errors.append("unsupported schema %r (expected %r)"
                      % (document.get("schema"), SUPPORTED_SCHEMA))
    version = document.get("schema_version")
    if not _is_int(version) or version < 1 or version > MAX_SUPPORTED_SCHEMA_VERSION:
        errors.append("unsupported schema_version %r (supported 1..%d)"
                      % (version, MAX_SUPPORTED_SCHEMA_VERSION))
    if not isinstance(document.get("features"), list):
        errors.append("bundle.features must be a list")
    if not isinstance(document.get("protocol"), dict):
        errors.append("bundle.protocol must be a mapping")
    return document, errors


def verify_integrity(bundle: dict) -> list:
    """重算规范化哈希；不采用证据自报的期望值。"""
    integrity = bundle.get("integrity")
    if not isinstance(integrity, dict):
        return ["bundle has no integrity block"]
    if integrity.get("algorithm") != "sha256":
        return ["unsupported integrity algorithm %r" % integrity.get("algorithm")]
    claimed = integrity.get("payload_sha256")
    if not isinstance(claimed, str) or len(claimed) != 64:
        return ["integrity.payload_sha256 must be a 64-char hex digest"]
    recomputed = fbe.bundle_digest(bundle)
    if recomputed != claimed:
        return ["integrity mismatch: payload sha256 %s != declared %s"
                % (recomputed[:16], claimed[:16])]
    return []


# ---------------------------------------------------------------- 契约复算

def expected_holds(entry: dict, actual: dict):
    """契约断言 vs 实际观测：True / False / None(无法判定)。

    `observed is None` 表示“没有拿到观测值”（探针 UNAVAILABLE / 观测点不存在），
    它既不能证明满足、也不能证明违反：返回 None -> INCOMPLETE。否则 `equals: true`
    会把“没观测到”误报成行为违规（Phase 1.56 测试 N19）。
    """
    observed = actual.get("observed")
    check = entry.get("check")
    if observed is None and ("equals" in entry or "min" in entry or "max" in entry):
        return None
    if check == "signal":
        if not _is_int(observed):
            return None
        if int(observed) != int(entry.get("count", 0)):
            return False
        if "last_args" in entry:
            return _args_match(actual.get("observed_args"), entry["last_args"])
        return True
    if "equals" in entry:
        return _value_equal(observed, entry["equals"], float(entry.get("tolerance", 0.0)))
    if "min" in entry or "max" in entry:
        if not _is_number(observed):
            return None
        value = float(observed)
        low = entry.get("min")
        high = entry.get("max")
        if low is not None and value < float(low):
            return False
        if high is not None and value > float(high):
            return False
        return True
    return None


def _observation_key(entry: dict) -> tuple:
    """检查项的语义键：signal 必须区分 entry，其余检查只按 check + target。"""
    check = str(entry.get("check") or "")
    target = str(entry.get("target") or ".")
    entry_name = str(entry.get("entry") or "") if check == "signal" else ""
    return check, target, entry_name


def _key_text(key: tuple) -> str:
    return "%s@%s%s" % (key[0], key[1], ("#" + key[2]) if key[2] else "")


def judge_record_keyed(record: dict, contract: dict) -> dict:
    """按键匹配的独立复核（Phase 1.68.2），不改变 judge_record 的既有语义。

    与旧判定器的区别：
    - 按 (check, target, signal-entry) 匹配，检查项顺序不影响结论；
    - 额外观测只记录在 extra_keys，不自动导致 INCOMPLETE/FAIL；
    - 缺失的契约检查项明确 INCOMPLETE；
    - 重复的实际观测键或契约键视为歧义，不静默去重；
    - 每个契约检查项都保留独立 verdict，便于 Attestation/Coverage 追溯。
    """
    result = check_result(STATUS_INCOMPLETE, "keyed_judge_uninitialised", "")
    result.update({"checks": [], "required_keys": [], "extra_keys": [],
                   "duplicate_actual_keys": [], "duplicate_contract_keys": []})
    if not isinstance(record, dict):
        result.update(reason="malformed_record",
                      detail="behavior record is not an object")
        return result
    if record.get("evidence") not in (None, fbe.EVIDENCE_BEHAVIOR):
        result.update(reason="unsupported_evidence_source",
                      detail="evidence source %r is not a registered behavior collector"
                      % record.get("evidence"))
        return result
    if not bool(record.get("action_executed")):
        result.update(reason="action_not_executed",
                      detail="the registered action never executed; state alone is not evidence")
        return result
    replay_count = record.get("replay_count")
    if not _is_int(replay_count) or replay_count < MIN_REPLAYS:
        result.update(reason="replay_missing",
                      detail="replay_count=%r < %d" % (replay_count, MIN_REPLAYS))
        return result
    if record.get("replay_consistent") is not True:
        result.update(reason="replay_inconsistent",
                      detail="replays disagreed; single-run agreement is not evidence")
        return result

    actual = record.get("actual")
    expected = contract.get("expected") or [] if isinstance(contract, dict) else []
    if not isinstance(expected, list) or not expected:
        result.update(reason="empty_contract",
                      detail="contract declares no evaluable expected checks")
        return result
    if not isinstance(actual, list):
        result.update(reason="observation_missing",
                      detail="record.actual is not a list")
        return result

    expected_by_key = {}
    duplicate_contract = []
    for index, entry in enumerate(expected):
        if not isinstance(entry, dict):
            result.update(reason="invalid_contract",
                          detail="contract.expected[%d] is not an object" % index)
            return result
        key = _observation_key(entry)
        if key in expected_by_key:
            duplicate_contract.append(_key_text(key))
            continue
        expected_by_key[key] = (index, entry)
    if duplicate_contract:
        result.update(reason="ambiguous_contract_key",
                      detail="contract repeats semantic key(s): %s"
                      % ", ".join(sorted(set(duplicate_contract))),
                      duplicate_contract_keys=sorted(set(duplicate_contract)))
        return result

    actual_by_key = {}
    duplicate_actual = []
    for index, item in enumerate(actual):
        if not isinstance(item, dict):
            result.update(reason="invalid_observation",
                          detail="record.actual[%d] is not an object" % index)
            return result
        key = _observation_key(item)
        if key in actual_by_key:
            duplicate_actual.append(_key_text(key))
            continue
        actual_by_key[key] = (index, item)

    result["required_keys"] = [_key_text(key) for key in expected_by_key]
    result["extra_keys"] = sorted(_key_text(key) for key in actual_by_key
                                  if key not in expected_by_key)
    result["duplicate_actual_keys"] = sorted(set(duplicate_actual))
    if duplicate_actual:
        result.update(reason="duplicate_observation_key",
                      detail="evidence repeats semantic key(s): %s; cannot decide which "
                             "observation is authoritative"
                      % ", ".join(sorted(set(duplicate_actual))))
        return result

    check_rows = []
    missing, failed, undecided = [], [], []
    for key, (index, entry) in expected_by_key.items():
        row = {"key": _key_text(key), "check": key[0], "target": key[1],
               "entry": key[2], "expected": entry, "observed": None,
               "verdict": STATUS_INCOMPLETE, "reason": ""}
        if key not in actual_by_key:
            row["reason"] = "observation_missing"
            missing.append(row["key"])
            check_rows.append(row)
            continue
        actual_index, item = actual_by_key[key]
        row["observed"] = item.get("observed")
        row["observed_args"] = item.get("observed_args")
        row["actual_index"] = actual_index
        verdict = expected_holds(entry, item)
        if verdict is None:
            row["reason"] = "observation_insufficient"
            undecided.append(row["key"])
        elif not verdict:
            row["verdict"] = STATUS_FAIL
            row["reason"] = "contract_violation"
            failed.append(row["key"])
        else:
            row["verdict"] = STATUS_PASS
            row["reason"] = "verified"
        check_rows.append(row)

    result["checks"] = check_rows
    if failed:
        result.update(status=STATUS_FAIL, reason="contract_violation",
                      detail="keyed checks failed: %s" % ", ".join(failed))
        return result
    if missing or undecided:
        result.update(status=STATUS_INCOMPLETE, reason="observation_incomplete",
                      detail="missing=%s undecided=%s"
                      % (", ".join(missing) or "-", ", ".join(undecided) or "-"))
        return result
    self_status = record.get("status")
    if self_status != fbe.STATUS_PASS:
        result.update(status=STATUS_INCOMPLETE, reason="evidence_self_contradiction",
                      detail="collector reported %r while keyed observations satisfy the "
                             "contract" % self_status)
        return result
    result.update(status=STATUS_PASS, reason="verified",
                  detail="recomputed from keyed contract and observations")
    return result


def judge_record(record: dict, contract: dict) -> dict:
    """单条行为证据 -> 独立复核结论（不读 record.status 作为通过依据）。"""
    if not isinstance(record, dict):
        return check_result(STATUS_INCOMPLETE, "malformed_record",
                            "behavior record is not an object")
    if record.get("evidence") not in (None, fbe.EVIDENCE_BEHAVIOR):
        return check_result(STATUS_INCOMPLETE, "unsupported_evidence_source",
                            "evidence source %r is not a registered behavior collector"
                            % record.get("evidence"))
    if not bool(record.get("action_executed")):
        return check_result(STATUS_INCOMPLETE, "action_not_executed",
                            "the registered action never executed; state alone is not evidence")
    replay_count = record.get("replay_count")
    if not _is_int(replay_count) or replay_count < MIN_REPLAYS:
        return check_result(STATUS_INCOMPLETE, "replay_missing",
                            "replay_count=%r < %d" % (replay_count, MIN_REPLAYS))
    if record.get("replay_consistent") is not True:
        return check_result(STATUS_INCOMPLETE, "replay_inconsistent",
                            "replays disagreed; single-run agreement is not evidence")

    actual = record.get("actual")
    expected = contract.get("expected") or []
    if not isinstance(actual, list):
        return check_result(STATUS_INCOMPLETE, "observation_missing",
                            "record.actual is not a list")
    if len(actual) != len(expected):
        return check_result(STATUS_INCOMPLETE, "observation_count_mismatch",
                            "observed %d check(s), contract declares %d"
                            % (len(actual), len(expected)))

    for index, entry in enumerate(expected):
        item = actual[index]
        if not isinstance(item, dict):
            return check_result(STATUS_INCOMPLETE, "observation_missing",
                                "check[%d] is not an object" % index)
        if item.get("check") != entry.get("check") \
                or str(item.get("target", "")) != str(entry.get("target", ".")):
            return check_result(STATUS_FAIL, "contract_violation",
                                "check[%d] target mismatch: evidence %s@%s vs contract %s@%s"
                                % (index, item.get("check"), item.get("target"),
                                   entry.get("check"), entry.get("target")))
        if entry.get("check") == "signal" \
                and str(item.get("entry", "")) != str(entry.get("entry", "")):
            return check_result(STATUS_FAIL, "contract_violation",
                                "check[%d] signal mismatch: evidence %r vs contract %r"
                                % (index, item.get("entry"), entry.get("entry")))
        verdict = expected_holds(entry, item)
        if verdict is None:
            return check_result(STATUS_INCOMPLETE, "observation_insufficient",
                                "check[%d] %s@%s has no decidable observation "
                                "(observed=%r)"
                                % (index, entry.get("check"), entry.get("target"),
                                   item.get("observed")))
        if not verdict:
            return check_result(STATUS_FAIL, "contract_violation",
                                "check[%d] %s@%s expected %r observed %r"
                                % (index, entry.get("check"), entry.get("target"),
                                   entry.get("equals", entry.get("count",
                                                                 {"min": entry.get("min"),
                                                                  "max": entry.get("max")})),
                                   item.get("observed")))

    self_status = record.get("status")
    if self_status != fbe.STATUS_PASS:
        # 观测能被重算为满足，但采集侧自称非 PASS：冲突必须暴露，不能升级为 PASS。
        return check_result(STATUS_INCOMPLETE, "evidence_self_contradiction",
                            "collector reported %r while the observation satisfies the "
                            "contract" % self_status)
    return check_result(STATUS_PASS, "verified", "recomputed from contract and observations")


# ---------------------------------------------------------------- 主流程

EVIDENCE_INDEX_NAME = "evidence_index.json"
EVIDENCE_INDEX_SCHEMA = "official_evidence_index"
EVIDENCE_INDEX_SCOPE = "official_contract"


def _norm_path(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def _index_path(evidence_dir: str) -> str:
    return os.path.join(evidence_dir, EVIDENCE_INDEX_NAME)


def load_evidence_index(evidence_dir: str) -> tuple:
    """读取可选的 Evidence Index；不存在时返回 (None, [])，保持旧目录扫描语义。"""
    path = _index_path(evidence_dir)
    if not os.path.isfile(path):
        return None, []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            document = json.load(handle)
    except OSError as exc:
        return None, ["evidence index unreadable: %s" % exc]
    except ValueError as exc:
        return None, ["evidence index is not valid JSON: %s" % exc]
    if not isinstance(document, dict):
        return None, ["evidence index must be a JSON object"]
    if document.get("schema") != EVIDENCE_INDEX_SCHEMA:
        return None, ["evidence index schema %r is not %r"
                      % (document.get("schema"), EVIDENCE_INDEX_SCHEMA)]
    if document.get("scope") != EVIDENCE_INDEX_SCOPE:
        return None, ["evidence index scope %r is not %r"
                      % (document.get("scope"), EVIDENCE_INDEX_SCOPE)]
    for field in ("active", "superseded", "unindexed", "conflicts"):
        if not isinstance(document.get(field), list):
            return None, ["evidence index %s must be a list" % field]
    return document, []


def _resolve_index_bundle(evidence_dir: str, relative: str):
    if not isinstance(relative, str) or not relative.strip():
        return None, "evidence index entry has no bundle_path"
    if os.path.isabs(relative):
        return None, "evidence index bundle_path must be relative: %r" % relative
    path = os.path.abspath(os.path.join(evidence_dir, relative.replace("/", os.sep)))
    root = os.path.abspath(evidence_dir)
    try:
        inside = os.path.commonpath([root, path]) == root
    except ValueError:
        inside = False
    if not inside:
        return None, "evidence index bundle_path escapes evidence dir: %r" % relative
    if not os.path.isfile(path):
        return None, "evidence index references a missing bundle: %r" % relative
    return path, ""


# ---------------------------------------------------------------- 主流程

def _bundle_documents(evidence_dir: str) -> tuple:
    """返回 (documents, errors, fatal)。

    有 `evidence_index.json` 时只加载 active Bundle；索引本身不改变 Bundle，
    superseded 仍保留审计。索引指向缺失文件、未登记 Bundle、同 ID 不同内容、
    非官方 Bundle 冒充官方、重复 active 声明等都属于 fatal 身份/完整性错误。
    没有索引时维持 Phase 1.56 的目录扫描语义（历史目录不受影响）。
    """
    if not os.path.isdir(evidence_dir):
        return [], ["evidence directory not found: %s" % evidence_dir], False
    index, index_errors = load_evidence_index(evidence_dir)
    if index_errors:
        return [], index_errors, True
    if index is not None:
        errors = []
        for item in index.get("conflicts") or []:
            errors.append("evidence index conflict: %s"
                          % json.dumps(item, ensure_ascii=False, sort_keys=True))
        for item in index.get("unindexed") or []:
            errors.append("evidence index has unindexed bundle: %s"
                          % json.dumps(item, ensure_ascii=False, sort_keys=True))
        active = index.get("active") or []
        paths, indexed = [], set()
        seen_ids = {}
        for entry in active:
            if not isinstance(entry, dict):
                errors.append("evidence index active entry is not an object")
                continue
            path, message = _resolve_index_bundle(
                evidence_dir, str(entry.get("bundle_path") or ""))
            if message:
                errors.append(message)
                continue
            key = _norm_path(path)
            if key in indexed:
                # 同一 active Bundle 重复登记：幂等，不制造虚假重复冲突。
                continue
            indexed.add(key)
            bundle_id = str(entry.get("bundle_id") or "")
            payload = str(entry.get("payload_sha256") or "")
            if bundle_id in seen_ids and seen_ids[bundle_id] != (key, payload):
                errors.append("evidence index reuses bundle id %r with different identity"
                              % bundle_id)
                continue
            seen_ids[bundle_id] = (key, payload)
            paths.append((path, entry))

        known = set(indexed)
        for item in index.get("superseded") or []:
            if not isinstance(item, dict):
                errors.append("evidence index superseded entry is not an object")
                continue
            path, message = _resolve_index_bundle(
                evidence_dir, str(item.get("bundle_path") or ""))
            if message:
                errors.append(message)
                continue
            known.add(_norm_path(path))
        for name in sorted(os.listdir(evidence_dir)):
            if not name.endswith(".json") or name.endswith(".sig.json"):
                continue
            if name == EVIDENCE_INDEX_NAME:
                continue
            path = os.path.join(evidence_dir, name)
            if os.path.isfile(path) and _norm_path(path) not in known:
                errors.append("evidence bundle is not registered in the index: %s" % name)
        if errors:
            return [], errors, True

        documents = []
        for path, entry in paths:
            name = os.path.basename(path)
            document, load_errors = load_bundle(path)
            item = {"path": path, "name": name, "document": document,
                    "errors": load_errors, "index_entry": entry}
            if document is not None:
                actual_id = str(document.get("bundle_id") or "")
                actual_payload = str((document.get("integrity") or {})
                                     .get("payload_sha256") or "")
                block = document.get("official_contract")
                if actual_id != str(entry.get("bundle_id") or ""):
                    load_errors.append("index bundle id %r != bundle id %r"
                                       % (entry.get("bundle_id"), actual_id))
                if actual_payload != str(entry.get("payload_sha256") or ""):
                    load_errors.append("index payload sha256 does not match bundle")
                if not isinstance(block, dict) or \
                        block.get("kind") != "OFFICIAL_CONTRACT":
                    load_errors.append("indexed bundle is not an OFFICIAL_CONTRACT bundle")
                if load_errors:
                    errors.append("%s: %s" % (name, "; ".join(load_errors)))
            documents.append(item)
        if errors:
            return [], errors, True
        return documents, [], False

    documents = []
    for name in sorted(os.listdir(evidence_dir)):
        if not name.endswith(".json"):
            continue
        if name.endswith(".sig.json"):
            # Phase 1.61：来源签名 sidecar（<bundle>.sig.json）不是证据包，
            # 不参与 Validator 的 bundle 校验；由 provenance 验证链单独消费。
            continue
        path = os.path.join(evidence_dir, name)
        if not os.path.isfile(path):
            continue
        document, errors = load_bundle(path)
        documents.append({"path": path, "name": name, "document": document,
                          "errors": errors})
    return documents, [], False


def _empty_result(status: str, reason: str, detail: str, targets) -> dict:
    targets = list(targets or [])
    return {"status": status, "reason": reason, "detail": detail,
            "checks": [], "bundles": [], "targets": targets,
            "summary": {"checked": 0, "pass": 0, "fail": 0, "incomplete": 0,
                        "features": len(targets), "bundles": 0, "skipped_features": [],
                        "artifacts": 0, "cross_validated": 0}}


def check_evidence(project_root: str = "", evidence_dir: str = "",
                   features=None, max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
                   protocol=None, protocol_path: str = "",
                   features_dir: str = "", now=None,
                   artifact_roots=None) -> dict:
    """证据目录 -> 结构化结论（PASS / FAIL / INCOMPLETE / ERROR）。"""
    project_root = project_root or PROJECT_ROOT
    evidence_dir = evidence_dir or DEFAULT_EVIDENCE_DIR
    features_dir = features_dir or instance_evidence.FEATURES_DIR
    current_time = now or datetime.now(timezone.utc)
    checks: list = []
    bundle_reports: list = []
    fatal: list = []
    # Phase 1.57：执行产物只允许来自显式授权的根目录（默认采集器的 .ai/tmp/behavior）。
    resolver = xval.ArtifactResolver(
        artifact_roots or xval.default_roots(project_root),
        base_dir=project_root, forbidden=[evidence_dir])
    used_artifacts: dict = {}
    cross_stats = {"artifacts": 0, "cross_validated": 0}

    try:
        if protocol is None:
            protocol = behavior_protocol.load_protocol(protocol_path or None)
    except behavior_protocol.ProtocolError as exc:
        return _empty_result(STATUS_ERROR, "protocol_invalid", str(exc), features)

    if not os.path.isdir(features_dir):
        # 环境缺失不是证据缺陷：整个 Feature 集合不可读时无法判定任何行为。
        return _empty_result(STATUS_INCOMPLETE, "features_unavailable",
                             "Features directory not found: %s" % features_dir, features)

    targets = list(features) if features else list(fbe.declared_features(features_dir))

    documents, dir_errors, dir_fatal = _bundle_documents(evidence_dir)
    if dir_errors:
        return _empty_result(STATUS_FAIL if dir_fatal else STATUS_INCOMPLETE,
                             "evidence_index_invalid" if dir_fatal else "evidence_unavailable",
                             "; ".join(dir_errors), targets)
    if not documents:
        return _empty_result(STATUS_INCOMPLETE, "no_evidence",
                             "no evidence bundle found in %s" % evidence_dir, targets)

    records = {}                 # (feature, behavior) -> [(bundle_id, record)]
    seen_bundle_ids = {}
    for item in documents:
        name = item["name"]
        document = item["document"]
        errors = list(item["errors"])
        entry = {"bundle": name, "status": STATUS_PASS, "reasons": []}

        if document is None:
            entry["status"] = STATUS_FAIL
            entry["reasons"] = errors or ["bundle_unreadable"]
            bundle_reports.append(entry)
            fatal.append("%s: %s" % (name, "; ".join(entry["reasons"])))
            continue

        integrity_errors = verify_integrity(document)
        if integrity_errors:
            entry["status"] = STATUS_FAIL
            entry["reasons"].extend(integrity_errors)
            fatal.append("%s: %s" % (name, "; ".join(integrity_errors)))

        declared = document.get("protocol") or {}
        if declared.get("protocol_version") != protocol.version:
            message = ("protocol version mismatch: evidence %r vs current %r"
                       % (declared.get("protocol_version"), protocol.version))
            entry["status"] = STATUS_FAIL
            entry["reasons"].append(message)
            fatal.append("%s: %s" % (name, message))
        elif declared.get("sha256"):
            current_hash = fbe._sha256_file(protocol_path or protocol.path)
            if current_hash and declared["sha256"] != current_hash:
                message = ("protocol content changed since the evidence was captured "
                           "(evidence %s vs current %s)"
                           % (declared["sha256"][:16], current_hash[:16]))
                entry["status"] = STATUS_FAIL
                entry["reasons"].append(message)
                fatal.append("%s: %s" % (name, message))

        generated = parse_timestamp(document.get("generated_at"))
        age_hours = None
        if generated is None:
            entry["status"] = STATUS_INCOMPLETE if entry["status"] == STATUS_PASS else entry["status"]
            entry["reasons"].append("generated_at is missing or not ISO-8601")
        else:
            age_hours = (current_time - generated).total_seconds() / 3600.0
            if age_hours > float(max_age_hours):
                message = ("evidence is %.1f h old (limit %.1f h); re-run the collector"
                           % (age_hours, float(max_age_hours)))
                if entry["status"] == STATUS_PASS:
                    entry["status"] = STATUS_INCOMPLETE
                entry["reasons"].append(message)
        entry["age_hours"] = None if age_hours is None else round(age_hours, 2)

        level = document.get("evidence_level")
        if level != SUPPORTED_LEVEL:
            message = ("unsupported evidence level %r (this stage verifies %r only)"
                       % (level, SUPPORTED_LEVEL))
            entry["status"] = STATUS_FAIL
            entry["reasons"].append(message)
            fatal.append("%s: %s" % (name, message))

        bundle_id = document.get("bundle_id")
        digest = (document.get("integrity") or {}).get("payload_sha256")
        if isinstance(bundle_id, str) and bundle_id:
            if bundle_id in seen_bundle_ids and seen_bundle_ids[bundle_id] != digest:
                message = "bundle id %r reused with different content" % bundle_id
                entry["status"] = STATUS_FAIL
                entry["reasons"].append(message)
                fatal.append("%s: %s" % (name, message))
            elif bundle_id in seen_bundle_ids:
                entry["reasons"].append("duplicate execution: bundle id %r captured twice"
                                        % bundle_id)
                if entry["status"] == STATUS_PASS:
                    entry["status"] = STATUS_INCOMPLETE
            seen_bundle_ids[bundle_id] = digest

        for feature_block in document.get("features") or []:
            if not isinstance(feature_block, dict):
                entry["status"] = STATUS_FAIL
                entry["reasons"].append("features[] must be objects")
                continue
            feature = str(feature_block.get("feature") or "")
            for record in feature_block.get("behaviors") or []:
                behavior = str((record or {}).get("behavior") or "")
                records.setdefault((feature, behavior), []).append((name, record))
        bundle_reports.append(entry)

    # ---- 目标 Feature 覆盖与契约复算 ----
    for feature in targets:
        feature_dir = os.path.join(features_dir, feature)
        if not os.path.isdir(feature_dir):
            checks.append({"feature": feature, "behavior": "", "evidence_level": SUPPORTED_LEVEL,
                           "validation_status": STATUS_FAIL,
                           "validation_reason": "unknown_feature",
                           "detail": "Features/%s does not exist" % feature})
            continue
        contracts, contract_reports = fbe.build_contracts(
            feature, features_dir, protocol=protocol)
        invalid = [report for report in contract_reports
                   if report.status == fbe.STATUS_INVALID]
        if invalid:
            checks.append({"feature": feature, "behavior": "", "evidence_level": SUPPORTED_LEVEL,
                           "validation_status": STATUS_FAIL,
                           "validation_reason": "contract_invalid",
                           "detail": "; ".join(report.detail for report in invalid)})
            continue

        declared_behaviors = {contract["behavior"] for contract in contracts}
        for contract in contracts:
            behavior = contract["behavior"]
            candidates = records.get((feature, behavior), [])
            if not candidates:
                checks.append({"feature": feature, "behavior": behavior,
                               "evidence_level": SUPPORTED_LEVEL,
                               "validation_status": STATUS_INCOMPLETE,
                               "validation_reason": "behavior_uncovered",
                               "detail": "no evidence for this declared behavior"})
                continue
            if len(candidates) > 1:
                digests = {json.dumps(record, sort_keys=True, ensure_ascii=False)
                           for _, record in candidates}
                if len(digests) > 1:
                    checks.append({"feature": feature, "behavior": behavior,
                                   "evidence_level": SUPPORTED_LEVEL,
                                   "validation_status": STATUS_FAIL,
                                   "validation_reason": "duplicate_conflict",
                                   "detail": "%d conflicting records for the same behavior"
                                             % len(candidates)})
                    continue
            _, record = candidates[0]
            verdict = judge_record(record, contract)
            cross = xval.cross_validate(record, contract, resolver, used=used_artifacts)
            artifacts = cross.get("artifacts") or []
            cross_stats["artifacts"] += len(artifacts)
            if artifacts and cross.get("status") != STATUS_FAIL:
                cross_stats["cross_validated"] += 1
            verdict = merge_verdicts(verdict, cross)
            checks.append({"feature": feature, "behavior": behavior,
                           "evidence_level": SUPPORTED_LEVEL,
                           "validation_status": verdict["status"],
                           "validation_reason": verdict["reason"],
                           "detail": verdict["detail"],
                           "artifacts": len(artifacts)})

        for (feature_name, behavior) in records:
            if feature_name == feature and behavior not in declared_behaviors:
                checks.append({"feature": feature, "behavior": behavior,
                               "evidence_level": SUPPORTED_LEVEL,
                               "validation_status": STATUS_FAIL,
                               "validation_reason": "unknown_behavior",
                               "detail": "behavior is not declared in "
                                         "Features/%s/template.yaml" % feature})
    # 目标集之外的 Feature：仓库里存在 = 未请求（跳过，不算失败）；仓库里不存在 = 拒绝。
    # `--feature` 的语义是“只验证这些 Feature”，不能因为同一个证据包（例如 --all 的
    # 产物）还包含其他 Feature 的记录就把它们判为错误（Phase 1.56 测试 P4）。
    known = set(targets)
    skipped_features = set()
    for (feature_name, behavior) in records:
        if feature_name in known:
            continue
        if os.path.isdir(os.path.join(features_dir, feature_name)):
            skipped_features.add(feature_name)
            continue
        checks.append({"feature": feature_name, "behavior": behavior,
                       "evidence_level": SUPPORTED_LEVEL,
                       "validation_status": STATUS_FAIL,
                       "validation_reason": "unknown_feature",
                       "detail": "evidence references a Feature that does not exist "
                                 "under %s" % features_dir})

    # 只保留注意：contract_invalid / unknown_feature 不重复报同一 feature
    deduped = []
    seen = set()
    for item in checks:
        key = (item["feature"], item["behavior"], item["validation_reason"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    checks = deduped

    statuses = [item["validation_status"] for item in checks]
    if fatal or STATUS_FAIL in statuses or any(
            bundle["status"] == STATUS_FAIL for bundle in bundle_reports):
        overall = STATUS_FAIL
        reason = "evidence_rejected"
    elif STATUS_INCOMPLETE in statuses or any(
            bundle["status"] == STATUS_INCOMPLETE for bundle in bundle_reports):
        overall = STATUS_INCOMPLETE
        reason = "verification_incomplete"
    elif not checks:
        overall = STATUS_INCOMPLETE
        reason = "no_targets"
    else:
        overall = STATUS_PASS
        reason = "verified"

    summary = {
        "checked": len(checks),
        "pass": statuses.count(STATUS_PASS),
        "fail": statuses.count(STATUS_FAIL),
        "incomplete": statuses.count(STATUS_INCOMPLETE),
        "features": len(targets),
        "bundles": len(bundle_reports),
        "skipped_features": sorted(skipped_features),
        "artifacts": cross_stats["artifacts"],
        "cross_validated": cross_stats["cross_validated"],
    }
    return {"status": overall, "reason": reason, "detail": "; ".join(fatal),
            "checks": checks, "bundles": bundle_reports, "targets": targets,
            "summary": summary}


def exit_code_for(status: str) -> int:
    return {STATUS_PASS: 0, STATUS_FAIL: 1, STATUS_INCOMPLETE: 2}.get(status, 3)


def format_report(result: dict) -> list:
    lines = ["Behavior Evidence (L4)"]
    lines.append("  bundles: %d, target features: %d"
                 % (result["summary"]["bundles"], result["summary"]["features"]))
    for item in result["checks"]:
        lines.append("  %-16s %-22s %-10s %s%s"
                     % (item["feature"], item["behavior"] or "-",
                        item["validation_status"], item["validation_reason"],
                        "" if not item["detail"] else " | " + item["detail"]))
    summary = result["summary"]
    lines.append("  pass=%d fail=%d incomplete=%d (checked=%d, artifacts=%d, "
                 "cross_validated=%d)"
                 % (summary["pass"], summary["fail"], summary["incomplete"],
                    summary["checked"], summary.get("artifacts", 0),
                    summary.get("cross_validated", 0)))
    skipped = summary.get("skipped_features") or []
    if skipped:
        lines.append("  skipped (not requested): %s" % ", ".join(skipped))
    for bundle in result["bundles"]:
        if bundle["status"] != STATUS_PASS:
            lines.append("  bundle %s: %s %s"
                         % (bundle["bundle"], bundle["status"],
                            "; ".join(bundle["reasons"])))
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate persisted Feature behavior evidence against the current "
                    "contracts (Phase 1.56).")
    parser.add_argument("--evidence-dir", default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--feature", action="append", default=[])
    parser.add_argument("--max-age-hours", type=float, default=DEFAULT_MAX_AGE_HOURS)
    parser.add_argument("--features-dir", default=instance_evidence.FEATURES_DIR)
    parser.add_argument("--protocol", default="")
    parser.add_argument("--artifact-root", action="append", default=[],
                        help="authorized execution artifact root (repeatable; default: "
                             ".ai/tmp/behavior)")
    parser.add_argument("--json", default="", help="write the machine-readable result here")
    args = parser.parse_args(argv)

    try:
        result = check_evidence(evidence_dir=args.evidence_dir, features=args.feature,
                                max_age_hours=args.max_age_hours,
                                features_dir=args.features_dir,
                                protocol_path=args.protocol,
                                artifact_roots=args.artifact_root)
    except Exception as exc:                       # noqa: BLE001 - 验证器自身异常必须可退出
        print("ERROR: behavior evidence stage failed: %s" % exc)
        return 3
    for line in format_report(result):
        print(line)
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        print("  json: %s" % args.json)
    return exit_code_for(result["status"])


if __name__ == "__main__":
    sys.exit(main())
