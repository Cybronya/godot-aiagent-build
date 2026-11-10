#!/usr/bin/env python3
"""Evaluation Evidence Adapter —— 让 Evaluation 消费 Validator 验证过的行为证据（Phase 1.58）。

定位：**单向适配层**，把 Validator（`.ai/tools/validator/check_behavior_evidence.py`）
已经给出的、逐 (Feature, Behavior) 的判定，转换成 Evaluation 可消费的标准化记录。

职责边界（不可混用）：

    Evidence Collector  = 记录行为执行事实（本模块不执行任何行为）
    Evidence Validator  = 判定证据有效性（本模块**不重新实现**，只调用其 Python API）
    Evaluation Adapter  = 把已验证证据转成评估输入（本模块）
    Evaluation Runner   = 按评估标准判断行为质量（`evidence_eval.py`）

三条硬约束：

1. **判定只来自 Validator**：`validator_status` 一律取自
   `check_behavior_evidence.check_evidence()` 的返回值；证据包里的 `status`
   字段只作为 provenance 记录，从不用于判定（采集侧自报不等于通过）。
2. **Validator PASS ≠ Evaluation PASS**：证据有效只说明观测可信；行为是否达标由
   Evaluation 声明的期望（`expect`）在同一批观察值上重算，规则复用 Validator 的
   `expected_holds`（同样的比较语义，但期望来自任务，而不是契约）。
3. **不确定就 INCOMPLETE**：观测缺失、期望无法决定、证据不足时返回 INCOMPLETE，
   绝不升级成 VERIFIED_PASS；证据被拒一律 INVALID_EVIDENCE，不计入普通行为失败。

本模块不做的事：不执行 Godot、不写证据包、不审批/更新 Baseline、不修改 Feature。

用法（由 `evidence_eval.py` 调用，也可在测试中直接调用）：

    import evidence_adapter
    verified = evidence_adapter.load_verified(".ai/tmp/p157/bundles_real")
    result = evidence_adapter.evaluate_task(task, verified, supported)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
PROJECT_ROOT = os.path.dirname(os.path.dirname(_TOOLS))
VALIDATOR_DIR = os.path.join(_TOOLS, "validator")
SCENE_COMPOSER = os.path.join(_TOOLS, "scene_composer")
for _path in (VALIDATOR_DIR, SCENE_COMPOSER, _TOOLS):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import check_behavior_evidence as stage                       # noqa: E402
import feature_behavior_evidence as fbe                       # noqa: E402

try:                                                          # Golden Trace 是可选依赖
    import trace_baselines as trace_baselines
except Exception:                                             # noqa: BLE001 - 缺模块不得影响证据评估
    trace_baselines = None

try:                                                          # Phase 1.60：Baseline 生命周期
    import baseline_lifecycle as baseline_lifecycle
except Exception:                                             # noqa: BLE001
    baseline_lifecycle = None

try:                                                          # Phase 1.60：Trace/Behavior 绑定
    import trace_bindings as trace_bindings
except Exception:                                             # noqa: BLE001
    trace_bindings = None

try:                                                          # Phase 1.61：来源签名验证
    from provenance import verification as provenance_verification
    from provenance.trust_store import TrustStore as provenance_TrustStore
except Exception:                                             # noqa: BLE001
    provenance_verification = None
    provenance_TrustStore = None

SCHEMA = "evaluation_evidence"
SCHEMA_VERSION = 1

# ---------------------------------------------------------------- Evaluation 状态
VERIFIED_PASS = "VERIFIED_PASS"
VERIFIED_FAIL = "VERIFIED_FAIL"
INVALID_EVIDENCE = "INVALID_EVIDENCE"
INCOMPLETE = "INCOMPLETE"
EVALUATION_ERROR = "EVALUATION_ERROR"
NOT_EVALUATED = "NOT_EVALUATED"

EVALUATION_STATUSES = (VERIFIED_PASS, VERIFIED_FAIL, INVALID_EVIDENCE,
                       INCOMPLETE, EVALUATION_ERROR, NOT_EVALUATED)

# 严重度：用于把多个 behavior 的结论折叠成一个任务结论（越大越严重）
_SEVERITY = {
    EVALUATION_ERROR: 5,
    INVALID_EVIDENCE: 4,
    VERIFIED_FAIL: 3,
    INCOMPLETE: 2,
    NOT_EVALUATED: 1,
    VERIFIED_PASS: 0,
}

# 评估模式（报告里必须可见，避免模式混算）
MODE_EVIDENCE = "evidence"           # Mode A：消费既有证据
MODE_PROBE = "probe"                 # Mode B：先跑采集器产生证据，再验证
MODE_LEGACY = "LEGACY_PROBE_ONLY"    # Mode C：旧 Probe-only 任务（不进入 VERIFIED_* 统计）

# 期望的三种结局：满足 / 不满足 / 无法判定
EXPECTATION_MET = "MET"
EXPECTATION_UNMET = "UNMET"
EXPECTATION_UNDECIDABLE = "UNDECIDABLE"

COUNTED_AS_PASS = (VERIFIED_PASS,)

# ---------------------------------------------------------------- Phase 1.61 签名门禁
# 默认关闭（trust_store=None）：1.58/1.60 语义逐字不变。
# 开启后（--require-signature / --allow-legacy）：Baseline 报告叠加外部信任根验签，
# Evidence 逐 bundle 验证 sidecar 签名；无效签名在任何模式下都拒绝。
_SIGNATURE_GATE: dict = {"trust_store": None, "policy": "allow_legacy",
                         "active": False}

# Evidence 签名策略 -> load_verified 的 provenance_policy 取值
PROVENANCE_OFF = ""                    # 不做来源验证（默认，完全兼容）
PROVENANCE_VERIFY = "verify"           # 诊断模式：签名存在则验证，无效即拒绝
PROVENANCE_REQUIRE = "require"         # 安全模式：缺签名也拒绝（不自动降级 Legacy）


def set_signature_gate(trust_store, policy: str = "allow_legacy") -> dict:
    """开启来源签名门禁（trust_store 必须指向工作区之外的外部信任根）。"""
    _SIGNATURE_GATE["trust_store"] = trust_store
    _SIGNATURE_GATE["policy"] = str(policy or "allow_legacy")
    _SIGNATURE_GATE["active"] = trust_store is not None
    return dict(_SIGNATURE_GATE)


def clear_signature_gate() -> None:
    """关闭来源签名门禁（回到 1.58/1.60 语义）。"""
    _SIGNATURE_GATE["trust_store"] = None
    _SIGNATURE_GATE["policy"] = "allow_legacy"
    _SIGNATURE_GATE["active"] = False


def signature_gate() -> dict:
    return dict(_SIGNATURE_GATE)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_status(value) -> str:
    """把任意输入收敛到状态词表；未知值 → EVALUATION_ERROR（不静默放行）。"""
    text = str(value or "").strip().upper()
    return text if text in EVALUATION_STATUSES else EVALUATION_ERROR


def severe(statuses) -> str:
    """折叠一组 Evaluation 状态：取最严重者；空集 → NOT_EVALUATED。"""
    cleaned = [normalize_status(item) for item in statuses]
    if not cleaned:
        return NOT_EVALUATED
    return max(cleaned, key=lambda item: _SEVERITY[item])


# ---------------------------------------------------------------- 正式支持集合

def supported_set(features_dir: str = "") -> dict:
    """动态读取正式支持的 Feature / Behavior 集合（不硬编码数量）。

    支持集 = 有 `template.yaml#behavior` 契约的 Feature（由采集器与 Validator 共用同一
    份推导逻辑 `fbe.declared_features` / `fbe.build_contracts`）。仅有目录但缺声明的
    Feature（例如 Phase 1.57 记录的 8 个上游未完成 Feature）不会自动进入支持集。
    """
    directory = features_dir or os.path.join(PROJECT_ROOT, "Features")
    features = list(fbe.declared_features(directory))
    mapping: dict[str, list[str]] = {}
    for feature in features:
        contracts, _reports = fbe.build_contracts(feature, directory)
        mapping[feature] = [str(contract["behavior"]) for contract in contracts]
    return {
        "features_dir": _relative(directory),
        "features": mapping,
        "feature_count": len(mapping),
        "behavior_count": sum(len(items) for items in mapping.values()),
        "source": "Features/*/template.yaml#behavior",
        "declared_features": features,
    }


def _relative(path: str) -> str:
    try:
        return os.path.relpath(os.path.abspath(path), PROJECT_ROOT).replace("\\", "/")
    except (OSError, ValueError):
        return path


# ---------------------------------------------------------------- 证据加载

def _provenance(evidence_dir: str) -> tuple[dict, list]:
    """只读地收集证据包的 provenance（bundle 身份 / 执行标识 / 产物摘要）。

    这不是验证：判定仍由 Validator 给出。provenance 的作用是让报告能追溯到
    具体 bundle、run_id 与 result.json，而不是只看到一个 PASS 字符串。
    """
    provenance: dict[tuple[str, str], dict] = {}
    bundle_index: list = []
    if not os.path.isdir(evidence_dir):
        return provenance, bundle_index
    for name in sorted(os.listdir(evidence_dir)):
        if not name.endswith(".json") or name.endswith(".sig.json"):
            # Phase 1.61：来源签名 sidecar 不是 bundle，不进 provenance/索引。
            continue
        path = os.path.join(evidence_dir, name)
        if not os.path.isfile(path):
            continue
        document, errors = stage.load_bundle(path)
        if document is None:
            bundle_index.append({"bundle": name, "readable": False,
                                 "errors": errors, "bundle_id": None})
            continue
        protocol = document.get("protocol") or {}
        integrity = document.get("integrity") or {}
        bundle_index.append({
            "bundle": name,
            "readable": True,
            "bundle_id": document.get("bundle_id"),
            "generated_at": document.get("generated_at"),
            "git_head": document.get("git_head"),
            "digest": integrity.get("payload_sha256"),
            "protocol_version": protocol.get("protocol_version"),
            "protocol_sha256": protocol.get("sha256"),
            "evidence_level": document.get("evidence_level"),
            "features": len(document.get("features") or []),
            "behaviors": sum(len(block.get("behaviors") or [])
                             for block in document.get("features") or []
                             if isinstance(block, dict)),
        })
        for block in document.get("features") or []:
            if not isinstance(block, dict):
                continue
            feature = str(block.get("feature") or "")
            for index, record in enumerate(block.get("behaviors") or []):
                if not isinstance(record, dict):
                    continue
                behavior = str(record.get("behavior") or "")
                entry = {
                    "bundle": name,
                    "bundle_id": document.get("bundle_id"),
                    "bundle_digest": integrity.get("payload_sha256"),
                    "generated_at": document.get("generated_at"),
                    "git_head": document.get("git_head"),
                    "protocol_version": protocol.get("protocol_version"),
                    "protocol_sha256": protocol.get("sha256"),
                    "evidence_level": document.get("evidence_level"),
                    "record_path": "features[%s].behaviors[%d]" % (feature, index),
                    "record": record,
                }
                provenance.setdefault((feature, behavior), []).append(entry)
    return provenance, bundle_index


def _execution_fields(entries: list) -> dict:
    """从 provenance 里抽取执行标识与产物摘要（多份同键记录时不合并，标记歧义）。"""
    if not entries:
        return {"available": False, "reason": "no_bundle_record"}
    if len(entries) > 1:
        # 同一 (Feature, Behavior) 出现多份记录：Validator 会判 duplicate_conflict /
        # duplicate execution，这里不挑一份“看起来更好”的，直接标记歧义。
        return {"available": False, "reason": "ambiguous_records",
                "bundle_ids": sorted({str(item.get("bundle_id")) for item in entries})}
    entry = entries[0]
    record = entry.get("record") or {}
    return {
        "available": True,
        "bundle": entry.get("bundle"),
        "bundle_id": entry.get("bundle_id"),
        "bundle_digest": entry.get("bundle_digest"),
        "bundle_generated_at": entry.get("generated_at"),
        "git_head": entry.get("git_head"),
        "protocol_version": entry.get("protocol_version"),
        "protocol_sha256": entry.get("protocol_sha256"),
        "evidence_level": entry.get("evidence_level"),
        "evidence_ref": "%s#%s" % (entry.get("bundle"), entry.get("record_path")),
        "run_id": record.get("run_id"),
        "replay_count": record.get("replay_count"),
        "replay_consistent": record.get("replay_consistent"),
        "action_executed": record.get("action_executed"),
        "evidence_paths": dict(record.get("evidence_paths") or {}),
        "artifact_digests": {key: dict(value) for key, value in
                             (record.get("artifact_digests") or {}).items()},
        # 采集侧自报状态只作 provenance，不参与判定
        "collector_status": record.get("status"),
    }


def load_verified(evidence_dir: str = "", features=None,
                  max_age_hours: float = stage.DEFAULT_MAX_AGE_HOURS,
                  artifact_roots=None, protocol_path: str = "",
                  features_dir: str = "", now=None,
                  provenance_policy: str = PROVENANCE_OFF) -> dict:
    """调用真实 Validator，把逐 (Feature, Behavior) 判定转换为 Evaluation 输入。

    Phase 1.61 加法参数 provenance_policy（默认 PROVENANCE_OFF = 1.58 语义不变）：

        ""        不做来源签名验证
        "verify"  每个可读 bundle 重算摘要并验证 sidecar 签名（<bundle>.sig.json）；
                  无签名 → 诊断 LEGACY_APPROVED；签名无效 → 该 bundle 判 FAIL
        "require" 同上，且**缺签名也判 FAIL**（安全模式，不自动降级 Legacy）

    验证是**追加**门禁：Evidence Integrity（1.56）与 Artifact Cross-Validation
    （1.57）先于并独立于签名验证执行，本参数不改变它们的判定。

    返回结构的字段语义：

        validator.status            Validator 总体结论（PASS / FAIL / INCOMPLETE / ERROR）
        behaviors[].validator_status 该 (Feature, Behavior) 的 Validator 结论
        behaviors[].execution       run_id / replay / evidence_paths / artifact_digests
        behaviors[].expected/actual 证据包里的契约期望与真实观测（转发，不重算）
    """
    project_root = PROJECT_ROOT
    evidence_dir = evidence_dir or stage.DEFAULT_EVIDENCE_DIR
    result = stage.check_evidence(project_root=project_root,
                                  evidence_dir=evidence_dir,
                                  features=list(features) if features else None,
                                  max_age_hours=max_age_hours,
                                  protocol_path=protocol_path,
                                  features_dir=features_dir,
                                  now=now,
                                  artifact_roots=artifact_roots)
    provenance, bundle_index = _provenance(evidence_dir)

    # ---- Phase 1.61：Evidence 来源签名验证（逐 bundle，sidecar）----
    if provenance_policy and provenance_verification is not None:
        gate = signature_gate()
        trust_store = gate.get("trust_store")
        if trust_store is None:
            trust_store = provenance_TrustStore(project_root=PROJECT_ROOT)
        for entry in bundle_index:
            if not entry.get("readable"):
                continue
            bundle_path = os.path.join(evidence_dir, str(entry.get("bundle") or ""))
            document, _load_errors = stage.load_bundle(bundle_path)
            if document is None:
                continue
            evaluated = provenance_verification.verify_evidence_bundle(
                bundle_path, document, trust_store=trust_store,
                signature_policy=("require_signature"
                                  if provenance_policy == PROVENANCE_REQUIRE
                                  else "allow_legacy"))
            entry["provenance_trust"] = evaluated["trust_level"]
            entry["provenance_usable"] = evaluated["usable"]
            entry["provenance_reason"] = (evaluated.get("verification") or {}).get("reason", "")
            entry["provenance_signer"] = (evaluated.get("verification") or {}).get("signer_subject")

    behaviors: list = []
    feature_errors: list = []
    seen: set = set()
    for check in result.get("checks") or []:
        feature = str(check.get("feature") or "")
        behavior = str(check.get("behavior") or "")
        if not behavior:
            feature_errors.append({"feature": feature,
                                   "validator_status": check.get("validation_status"),
                                   "reason": check.get("validation_reason"),
                                   "detail": check.get("detail", "")})
            continue
        key = (feature, behavior)
        seen.add(key)
        entries = provenance.get(key) or []
        execution = _execution_fields(entries)
        record = (entries[0].get("record") or {}) if len(entries) == 1 else {}
        behaviors.append({
            "feature": feature,
            "behavior": behavior,
            "validator_status": check.get("validation_status"),
            "validator_reason": check.get("validation_reason"),
            "validator_detail": check.get("detail", ""),
            "artifacts": int(check.get("artifacts") or 0),
            "execution": execution,
            "expected": list(record.get("expected") or []),
            "actual": list(record.get("actual") or []),
        })

    # 证据里出现、但当前契约里没有的 behavior：Validator 已判 FAIL unknown_behavior，
    # 这里补一条供覆盖对账使用（不重复计入 behaviors 的统计键）。
    undeclared: list = []
    # 证据包级别的问题（摘要不符 / 协议变更 / 过期 / bundle_id 复用）会让 Validator 的
    # 总体结论变 FAIL/INCOMPLETE，但逐 behavior 的契约复算可能仍然 PASS。绝不能因为
    # 逐条复算通过就忽略包级拒绝：按包级结论把对应的 behavior 降级。
    bundle_status = {str(entry.get("bundle")): (entry.get("status"),
                                                 list(entry.get("reasons") or []))
                     for entry in result.get("bundles") or []}
    # Phase 1.61：来源签名失败（无效签名）在任何模式下都拒绝；require 模式下
    # 缺签名同样拒绝（不静默降级 Legacy）。这是对 1.56/1.57 判定的**追加**降级，
    # 不改变 Integrity / Cross-Validation 本身的结论。
    for entry in bundle_index:
        if entry.get("provenance_trust") is None:
            continue
        if entry.get("provenance_usable"):
            continue  # CRYPTOGRAPHICALLY_VERIFIED / LEGACY_APPROVED（诊断模式）
        bundle_status[str(entry.get("bundle"))] = (
            stage.STATUS_FAIL,
            ["provenance_%s: %s" % (str(entry.get("provenance_trust")).lower(),
                                    entry.get("provenance_reason") or "")])
    for item in behaviors:
        sources = provenance.get((item["feature"], item["behavior"])) or []
        statuses = [bundle_status.get(str(source.get("bundle"))) for source in sources]
        if any(status == stage.STATUS_FAIL for status, _reasons in statuses if status):
            reasons = [reason for status, items in statuses if status == stage.STATUS_FAIL
                       for reason in items]
            item["validator_status"] = "FAIL"
            item["validator_reason"] = "bundle_rejected"
            item["validator_detail"] = "; ".join(reasons)
        elif any(status == stage.STATUS_INCOMPLETE for status, _reasons in statuses if status) \
                and item["validator_status"] == "PASS":
            reasons = [reason for status, items in statuses
                       if status == stage.STATUS_INCOMPLETE for reason in items]
            item["validator_status"] = "INCOMPLETE"
            item["validator_reason"] = "bundle_incomplete"
            item["validator_detail"] = "; ".join(reasons)
    for (feature, behavior) in provenance:
        if (feature, behavior) in seen:
            continue
        entries = provenance[(feature, behavior)]
        undeclared.append({
            "feature": feature,
            "behavior": behavior,
            "bundle": entries[0].get("bundle") if entries else None,
            "run_id": (entries[0].get("record") or {}).get("run_id") if entries else None,
        })

    summary = result.get("summary") or {}
    protocol_versions = sorted({str(item.get("protocol_version"))
                                for item in bundle_index if item.get("protocol_version")})
    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_iso(),
        "source": "behavior_evidence",
        "evidence_dir": _relative(evidence_dir),
        "adapter": {"module": "evaluation/evidence_adapter", "version": SCHEMA_VERSION,
                    "validator": "validator/check_behavior_evidence",
                    "verdict_source": "validator"},
        "validator": {
            "status": result.get("status"),
            "reason": result.get("reason"),
            "detail": result.get("detail", ""),
            "summary": summary,
            "targets": list(result.get("targets") or []),
            "bundles": list(result.get("bundles") or []),
            "protocol_versions": protocol_versions,
        },
        "behaviors": behaviors,
        "feature_errors": feature_errors,
        "undeclared_behaviors": undeclared,
        "bundle_index": bundle_index,
        "coverage": {
            "evidence_records": len(provenance),
            "validator_checked": int(summary.get("checked") or 0),
            "validator_pass": int(summary.get("pass") or 0),
            "validator_fail": int(summary.get("fail") or 0),
            "validator_incomplete": int(summary.get("incomplete") or 0),
            "artifacts": int(summary.get("artifacts") or 0),
            "cross_validated": int(summary.get("cross_validated") or 0),
            "undeclared_behaviors": len(undeclared),
        },
    }


# ---------------------------------------------------------------- 状态模型

def evaluation_status(validator_status, expectation_state=None) -> tuple[str, str]:
    """(Validator 结论, 期望结论) -> (Evaluation 状态, 原因)。

    转换表（非法组合一律拒绝，返回 EVALUATION_ERROR 而不是硬凑一个状态）：

        PASS       + MET          -> VERIFIED_PASS
        PASS       + UNMET        -> VERIFIED_FAIL
        PASS       + UNDECIDABLE  -> INCOMPLETE
        FAIL       + 任意         -> INVALID_EVIDENCE
        INCOMPLETE + 任意         -> INCOMPLETE
        ERROR      + 任意         -> EVALUATION_ERROR
        其它                       -> EVALUATION_ERROR（illegal_transition）
    """
    validator = str(validator_status or "").strip().upper()
    state = str(expectation_state or "").strip().upper()

    if validator == "FAIL":
        return INVALID_EVIDENCE, "validator_rejected_evidence"
    if validator == "INCOMPLETE":
        return INCOMPLETE, "validator_incomplete"
    if validator == "ERROR":
        return EVALUATION_ERROR, "validator_error"
    if validator == "PASS":
        if state == EXPECTATION_MET:
            return VERIFIED_PASS, "verified"
        if state == EXPECTATION_UNMET:
            return VERIFIED_FAIL, "behavior_mismatch"
        if state == EXPECTATION_UNDECIDABLE:
            return INCOMPLETE, "expectation_undecidable"
        if not state:
            # 证据有效但没有任何评估期望：不能当成通过。
            return EVALUATION_ERROR, "expectation_missing"
    return EVALUATION_ERROR, "illegal_transition"


def evaluate_expectations(expectations, actual) -> dict:
    """在**观测值**上重算 Evaluation 期望（不看采集侧自报的 status）。

    期望项与观测项按 (check, target, entry) 精确对应；比较语义复用 Validator 的
    `expected_holds`（同一套 equals / count / min / max / last_args 规则），区别只在
    期望来自 Evaluation 任务而不是 Feature 契约。
    """
    items = [item for item in (actual or []) if isinstance(item, dict)]
    checks: list = []
    state = EXPECTATION_MET
    problems: list = []
    for expectation in expectations or []:
        if not isinstance(expectation, dict):
            checks.append({"expectation": expectation, "state": EXPECTATION_UNDECIDABLE,
                           "detail": "expectation is not an object"})
            state = EXPECTATION_UNDECIDABLE
            problems.append("malformed expectation")
            continue
        key = (str(expectation.get("check") or ""),
               str(expectation.get("target", ".")),
               str(expectation.get("entry", "")))
        match = None
        for item in items:
            candidate = (str(item.get("check") or ""),
                         str(item.get("target", ".")),
                         str(item.get("entry", "")))
            if candidate == key:
                match = item
                break
        if match is None:
            checks.append({"check": key[0], "target": key[1], "entry": key[2],
                           "state": EXPECTATION_UNDECIDABLE,
                           "detail": "no observation for this check"})
            if state == EXPECTATION_MET:
                state = EXPECTATION_UNDECIDABLE
            problems.append("%s@%s: no observation" % (key[0], key[1]))
            continue
        verdict = stage.expected_holds(expectation, match)
        if verdict is None:
            checks.append({"check": key[0], "target": key[1], "entry": key[2],
                           "observed": match.get("observed"),
                           "state": EXPECTATION_UNDECIDABLE,
                           "detail": "observation is not decidable against the expectation"})
            if state == EXPECTATION_MET:
                state = EXPECTATION_UNDECIDABLE
            problems.append("%s@%s: undecidable" % (key[0], key[1]))
            continue
        checks.append({"check": key[0], "target": key[1], "entry": key[2],
                       "observed": match.get("observed"),
                       "observed_args": match.get("observed_args"),
                       "expected": {name: expectation[name] for name in
                                    ("equals", "count", "min", "max", "last_args")
                                    if name in expectation},
                       "state": EXPECTATION_MET if verdict else EXPECTATION_UNMET})
        if not verdict:
            state = EXPECTATION_UNMET
            problems.append("%s@%s: expectation not met" % (key[0], key[1]))
    if not expectations:
        return {"state": EXPECTATION_UNDECIDABLE, "checks": [],
                "detail": "task declares no expectation"}
    return {"state": state, "checks": checks, "detail": "; ".join(problems)}


# ---------------------------------------------------------------- 任务映射

def normalize_task(task: dict) -> list:
    """任务 -> [{'behavior', 'expect', 'label'}]（单 behavior 与多 behavior 统一）。"""
    specs: list = []
    if task.get("behavior"):
        specs.append({"behavior": str(task["behavior"]),
                      "expect": list(task.get("expect") or []),
                      "label": str(task["behavior"])})
    for item in task.get("behaviors") or []:
        if isinstance(item, str):
            specs.append({"behavior": item, "expect": list(task.get("expect") or []),
                          "label": item})
        elif isinstance(item, dict) and item.get("behavior"):
            specs.append({"behavior": str(item["behavior"]),
                          "expect": list(item.get("expect") or []),
                          "label": str(item.get("behavior"))})
    return specs


def duplicate_mappings(tasks) -> list:
    """同一 (Feature, Behavior) 被多个任务映射 -> 会重复统计，必须拒绝。"""
    seen: dict = {}
    problems: list = []
    for task in tasks:
        feature = str(task.get("feature") or "")
        for spec in normalize_task(task):
            key = (feature, spec["behavior"])
            if key in seen and seen[key] != task.get("id"):
                problems.append("%s and %s both map %s/%s"
                                % (seen[key], task.get("id"), feature, spec["behavior"]))
            seen[key] = task.get("id")
    return problems


def binding_gate(validation: dict) -> tuple[str, str] | None:
    """绑定验证结果 -> (Evaluation 状态, 原因)；VALID_BINDING 返回 None。

    映射（任务书 §6，缺 bindings 不判定）：缺失绑定 -> INCOMPLETE；
    失效 / 冲突 / 不可信 Baseline -> NOT_EVALUATED（绝不升级成 VERIFIED_*）。
    """
    if trace_bindings is None:
        return None
    status = str(validation.get("status") or trace_bindings.NOT_APPLICABLE)
    if status == trace_bindings.VALID_BINDING:
        return None
    if status == trace_bindings.MISSING_BINDING:
        return INCOMPLETE, "binding_missing"
    mapping = {
        trace_bindings.UNAPPROVED_BASELINE: ("baseline_unapproved", NOT_EVALUATED),
        trace_bindings.REVOKED_BASELINE: ("baseline_revoked", NOT_EVALUATED),
        trace_bindings.DIGEST_MISMATCH: ("baseline_digest_mismatch", NOT_EVALUATED),
        "APPROVAL_MISMATCH": ("baseline_approval_mismatch", NOT_EVALUATED),
        trace_bindings.STALE_BINDING: ("binding_stale", NOT_EVALUATED),
        trace_bindings.SCENARIO_MISMATCH: ("binding_scenario_mismatch", NOT_EVALUATED),
        trace_bindings.CONTRACT_MISMATCH: ("binding_contract_mismatch", NOT_EVALUATED),
        trace_bindings.INVALID_BINDING: ("binding_invalid", NOT_EVALUATED),
    }
    if status in mapping:
        reason, state = mapping[status]
        return state, reason
    return NOT_EVALUATED, "binding_%s" % status.lower()


def _contract_expected(feature: str, behavior: str, supported: dict):
    """读取当前契约的 expected 列表（用于绑定预期不得改宽的校验）。"""
    features_dir = os.path.join(PROJECT_ROOT, supported.get("features_dir") or "Features") \
        if not os.path.isabs(str(supported.get("features_dir") or "")) \
        else str(supported.get("features_dir"))
    try:
        contracts, _reports = fbe.build_contracts(feature, features_dir)
    except Exception:                                        # noqa: BLE001 - 契约不可读不阻塞
        return None
    for contract in contracts:
        if str(contract.get("behavior")) == str(behavior):
            return list(contract.get("expected") or [])
    return None


def evaluate_task(task: dict, verified: dict, supported: dict,
                  holdout: bool = False, bindings: dict | None = None) -> dict:
    """单个 Evaluation 任务 -> 结论（证据有效性 + 行为是否符合期望）。"""
    task_id = str(task.get("id") or "?")
    feature = str(task.get("feature") or "")
    record: dict = {
        "task_id": task_id,
        "title": str(task.get("title") or ""),
        "feature_id": feature,
        "behavior_id": "|".join(spec["behavior"] for spec in normalize_task(task)),
        "evaluation_mode": MODE_EVIDENCE if not task.get("mode") else str(task["mode"]),
        "holdout": bool(holdout or task.get("holdout")),
        "golden_trace": None,
        "behaviors": [],
    }

    if feature not in (supported.get("features") or {}):
        record.update({"evaluation_status": EVALUATION_ERROR,
                       "reason": "unknown_feature",
                       "detail": "Feature %r has no declared behavior contract" % feature})
        return record

    index = {(item["feature"], item["behavior"]): item
             for item in verified.get("behaviors") or []}
    specs = normalize_task(task)
    if not specs:
        record.update({"evaluation_status": EVALUATION_ERROR,
                       "reason": "empty_mapping",
                       "detail": "task declares neither behavior nor behaviors[]"})
        return record

    results: list = []
    for spec in specs:
        behavior = spec["behavior"]
        if behavior not in (supported["features"].get(feature) or []):
            results.append({"behavior": behavior,
                            "evaluation_status": EVALUATION_ERROR,
                            "reason": "unknown_behavior",
                            "detail": "Behavior %r is not declared by Features/%s"
                                      % (behavior, feature)})
            continue
        item = index.get((feature, behavior))
        if item is None:
            results.append({"behavior": behavior,
                            "evaluation_status": INCOMPLETE,
                            "reason": "no_evidence",
                            "detail": "no evidence record for this behavior"})
            continue

        # ---- Phase 1.60：Trace/Behavior 绑定验证 --------------------------
        # 任务可声明 expected_source（task 级或 behavior 级）；声明了来源时，
        # 期望必须来自有效绑定，绑定缺失/失效直接门禁（不评估任务自带的 expect）。
        # 未声明来源的任务保持 Phase 1.58 语义不变，绑定只作诊断字段。
        expected_source = str(task.get("expected_source")
                              or spec.get("expected_source") or "")
        binding_validation = None
        expectation_items = spec["expect"]
        if (bindings is not None or expected_source) and trace_bindings is not None:
            binding = trace_bindings.get_binding(bindings or {}, feature, behavior)
            scenario_id = ""
            trace_decl = task.get("trace") or {}
            if isinstance(trace_decl, dict):
                scenario_id = str(trace_decl.get("scenario") or "")
            baseline_rep = None
            if binding and binding.get("baseline_id"):
                baseline_rep = baseline_report(
                    scenario=str(binding.get("scenario_id") or ""),
                    path=str(binding.get("baseline_path") or ""))
            binding_validation = trace_bindings.validate_binding(
                binding, feature_id=feature, behavior_id=behavior,
                scenario_id=scenario_id,
                contract_version=str(task.get("contract_version") or ""),
                contract_expected=_contract_expected(feature, behavior, supported)
                if binding is not None else None,
                baseline_report=baseline_rep)
            if expected_source:
                gate = binding_gate(binding_validation)
                if gate is not None:
                    results.append({"behavior": behavior,
                                    "evaluation_status": gate[0],
                                    "reason": gate[1],
                                    "detail": binding_validation.get("reason", ""),
                                    "binding_status": binding_validation.get("status"),
                                    "expected_source": expected_source,
                                    "validator_status": item.get("validator_status")})
                    continue
                # 来源声明有效：期望取自绑定（binding expected 已验证不宽于契约）
                expectation_items = list(binding.get("expected") or [])

        expectation = evaluate_expectations(expectation_items, item.get("actual"))
        status, reason = evaluation_status(item.get("validator_status"),
                                           expectation["state"])
        execution = item.get("execution") or {}
        results.append({
            "behavior": behavior,
            "evaluation_status": status,
            "reason": reason,
            "detail": expectation["detail"] or item.get("validator_detail", ""),
            "binding_status": (binding_validation or {}).get("status"),
            "expected_source": expected_source or (binding_validation or {}).get("expected_source"),
            "validator_status": item.get("validator_status"),
            "validator_reason": item.get("validator_reason"),
            "expectation": expectation,
            "execution_id": execution.get("run_id"),
            "replay_count": execution.get("replay_count"),
            "replay_consistent": execution.get("replay_consistent"),
            "evidence_bundle_ref": execution.get("evidence_ref"),
            "evidence_bundle_id": execution.get("bundle_id"),
            "bundle_digest": execution.get("bundle_digest"),
            "artifact_digests": execution.get("artifact_digests") or {},
            "evidence_paths": execution.get("evidence_paths") or {},
            "protocol_version": execution.get("protocol_version"),
            "artifacts": item.get("artifacts"),
        })

    record["behaviors"] = results
    record["evaluation_status"] = severe([item["evaluation_status"] for item in results])
    record["validator_status"] = severe_validator([item.get("validator_status")
                                                   for item in results])
    if record["evaluation_status"] != VERIFIED_PASS:
        record["reason"] = results[0].get("reason", "") if len(results) == 1 else "mixed"
        record["detail"] = "; ".join(
            "%s: %s %s" % (item["behavior"], item["evaluation_status"], item.get("detail", ""))
            for item in results if item["evaluation_status"] != VERIFIED_PASS)
    return record


def severe_validator(statuses) -> str:
    """任务的 Validator 侧汇总：FAIL 优先，其次 INCOMPLETE，最后 PASS。"""
    cleaned = [str(item or "").upper() for item in statuses if item]
    for candidate in ("FAIL", "INCOMPLETE", "ERROR"):
        if candidate in cleaned:
            return candidate
    return "PASS" if cleaned else ""


# ---------------------------------------------------------------- Golden Trace

def baseline_report(path: str = "", scenario: str = "") -> dict:
    """读取已批准的 Golden Trace Baseline，报告绑定与版本（不比较、不改写）。"""
    if trace_baselines is None:
        return {"status": "EVALUATION_ERROR", "reason": "trace_module_unavailable"}
    target = path or (os.path.join(VALIDATOR_DIR, "baselines", "%s.json" % scenario)
                      if scenario else "")
    if not target or not os.path.isfile(target):
        return {"status": INCOMPLETE, "reason": "baseline_missing",
                "baseline_path": _relative(target) if target else ""}
    try:
        with open(target, "r", encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError) as exc:
        return {"status": "INVALID_BASELINE", "reason": "baseline_unreadable",
                "baseline_path": _relative(target), "detail": str(exc)}
    errors = trace_baselines.validate_baseline(document)
    approval = document.get("approval") or {}
    report = {
        "baseline_path": _relative(target),
        "baseline_id": document.get("scenario_id"),
        "baseline_version": document.get("baseline_version"),
        "baseline_schema_version": document.get("baseline_schema_version"),
        "trace_schema_version": document.get("trace_schema_version"),
        "approved_behavior_version": document.get("approved_behavior_version"),
        "approval_status": approval.get("status"),
        "approver": approval.get("approver"),
        "approved_at": approval.get("approved_at"),
        "event_count": len(document.get("events") or []),
        # 现有基线只覆盖「编排场景」，不含 Feature / Behavior 绑定：不能假装能逐行为比较。
        "binding": "scenario_only",
        "feature": None,
        "behavior": None,
        "status": None,
        "reason": "",
    }
    report["validation_errors"] = [str(item) for item in errors[:3]]
    # 结构/语义损坏优先于「未审批」：损坏的文档不能被误报成只是没批。
    structural = [item for item in errors if "approval.status" not in str(item)]
    if structural:
        report["status"] = "INVALID_BASELINE"
        report["reason"] = "; ".join(str(item) for item in structural[:3])
        return report
    if str(approval.get("status")) != "approved":
        report["status"] = "BASELINE_UNAPPROVED"
        report["reason"] = "baseline approval status is %r (must be 'approved')" \
                           % approval.get("status")
        return report
    # Phase 1.60：使用时复核——重算内容摘要并与审批登记比对。
    # 审批后修改基线内容（保留合法 approval 块）在这里被拒绝；没有登记记录的
    # 基线（含未迁移的旧数据）不判定为可信，不自动升级。
    if baseline_lifecycle is not None:
        gate = signature_gate()
        if gate.get("active") and baseline_lifecycle is not None:
            lifecycle = baseline_lifecycle.use_baseline_trusted(
                document, baseline_path=target,
                trust_store=gate.get("trust_store"),
                signature_policy=gate.get("policy") or "allow_legacy")
        else:
            lifecycle = baseline_lifecycle.use_baseline(document, baseline_path=target)
        report["lifecycle_status"] = lifecycle.get("status")
        report["content_digest"] = lifecycle.get("content_digest")
        report["registered_digest"] = lifecycle.get("registered_digest")
        if lifecycle.get("provenance_trust"):
            report["provenance_trust"] = lifecycle.get("provenance_trust")
            report["provenance"] = lifecycle.get("provenance")
        if lifecycle.get("status") != "APPROVED_OK":
            report["status"] = {
                "UNAPPROVED": "BASELINE_UNAPPROVED",
                "MISSING_REGISTRATION": INCOMPLETE,
                "REVOKED": "REVOKED_BASELINE",
                "SUPERSEDED": "SUPERSEDED_BASELINE",
                "DIGEST_MISMATCH": "DIGEST_MISMATCH",
                "INVALID_BASELINE": "INVALID_BASELINE",
                "SIGNATURE_REQUIRED": "SIGNATURE_REQUIRED",
                "SIGNATURE_INVALID": "SIGNATURE_INVALID",
            }.get(lifecycle.get("status"), "INVALID_BASELINE")
            report["reason"] = lifecycle.get("reason") or "baseline lifecycle check failed"
            return report
    report["status"] = "PASS"
    report["reason"] = "approved baseline metadata is valid"
    return report


def compare_with_baseline(baseline_path: str, trace_path: str) -> dict:
    """把真实 trace 与已批准基线逐事件比较（复用 Validator 的比较器，不复制规则）。"""
    if trace_baselines is None:
        return {"status": "EVALUATION_ERROR", "reason": "trace_module_unavailable"}
    try:
        with open(baseline_path, "r", encoding="utf-8") as handle:
            baseline = json.load(handle)
        with open(trace_path, "r", encoding="utf-8") as handle:
            trace = json.load(handle)
    except (OSError, ValueError) as exc:
        return {"status": INCOMPLETE, "reason": "unreadable_input", "detail": str(exc)}
    result = trace_baselines.compare(baseline, trace, baseline_path=_relative(baseline_path))
    return {
        "status": result.get("status"),
        "scenario_id": result.get("scenario_id"),
        "baseline_version": result.get("baseline_version"),
        "approved_behavior_version": result.get("approved_behavior_version"),
        "expected_event_count": result.get("expected_event_count"),
        "actual_event_count": result.get("actual_event_count"),
        "matched_event_count": result.get("matched_event_count"),
        "first_difference": result.get("first_difference"),
        "differences": result.get("differences") or [],
        "summary": result.get("summary", ""),
    }


# ---------------------------------------------------------------- Holdout

def batch_identity(item: dict) -> dict:
    """一个 behavior 记录所属的执行批次标识（bundle_id + run_id）。"""
    execution = item.get("execution") or {}
    return {"bundle_id": execution.get("bundle_id"),
            "run_id": execution.get("run_id"),
            "evidence_ref": execution.get("evidence_ref")}


def holdout_isolation(training: dict, holdout: dict) -> list:
    """训练证据与 Holdout 证据的批次隔离检查（不允许同一批次两边都用）。"""
    problems: list = []
    train_bundles = {item.get("bundle_id") for item in
                     (training.get("bundle_index") or []) if item.get("bundle_id")}
    hold_bundles = {item.get("bundle_id") for item in
                    (holdout.get("bundle_index") or []) if item.get("bundle_id")}
    shared_bundles = sorted(train_bundles & hold_bundles)
    if shared_bundles:
        problems.append("bundle(s) used as both training and holdout evidence: %s"
                        % ", ".join(shared_bundles))
    train_runs = {str((item.get("execution") or {}).get("run_id"))
                  for item in training.get("behaviors") or []}
    hold_runs = {str((item.get("execution") or {}).get("run_id"))
                 for item in holdout.get("behaviors") or []}
    shared_runs = sorted(run for run in (train_runs & hold_runs) if run and run != "None")
    if shared_runs:
        problems.append("execution run_id(s) used on both sides: %s"
                        % ", ".join(shared_runs))
    return problems


# ---------------------------------------------------------------- 汇总

def summarize(task_results, verified: dict, legacy_tasks=(), supported=None,
              holdout_results=()) -> dict:
    """报告指标：证据有效性与行为评估**分开统计**，Holdout 独立成块。"""
    main = [item for item in task_results]
    counts = {status: 0 for status in EVALUATION_STATUSES}
    for item in main:
        counts[normalize_status(item.get("evaluation_status"))] += 1
    holdout_items = list(holdout_results)
    holdout_counts = {status: 0 for status in EVALUATION_STATUSES}
    for item in holdout_items:
        holdout_counts[normalize_status(item.get("evaluation_status"))] += 1
    validation = (verified.get("validator") or {}).get("summary") or {}
    bundles = verified.get("validator", {}).get("bundles") or []
    bundle_counts = {status: 0 for status in ("PASS", "FAIL", "INCOMPLETE")}
    rejected = []
    for entry in bundles:
        status = str(entry.get("status") or "INCOMPLETE")
        bundle_counts[status] = bundle_counts.get(status, 0) + 1
        if status != "PASS":
            rejected.append({"bundle": entry.get("bundle"), "status": status,
                             "reasons": list(entry.get("reasons") or [])[:3]})
    return {
        "evidence_validation": {
            "status": (verified.get("validator") or {}).get("status"),
            "checked": int(validation.get("checked") or 0),
            "pass": int(validation.get("pass") or 0),
            "fail": int(validation.get("fail") or 0),
            "incomplete": int(validation.get("incomplete") or 0),
            "artifacts": int(validation.get("artifacts") or 0),
            "cross_validated": int(validation.get("cross_validated") or 0),
            # 逐条复算 pass 而包级被拒时（摘要不符/过期/协议变更），单独把包级结论列出来，
            # 避免 “pass=N fail=0” 被误读成整包有效。
            "bundles": bundle_counts,
            "rejected_bundles": rejected,
        },
        "behavior_evaluation": dict(counts),
        "behavior_evaluation_total": len(main),
        "holdout": dict(holdout_counts, total=len(holdout_items)),
        "coverage": coverage_gap(main, verified, legacy_tasks, supported),
        "legacy_probe_only": len(list(legacy_tasks)),
    }


def coverage_gap(task_results, verified: dict, legacy_tasks=(), supported=None) -> dict:
    """集合对账：支持集 / 证据集 / 评估集 / Golden Trace 集 / Holdout 集。"""
    supported = supported or {}
    supported_behaviors = {(feature, behavior)
                           for feature, behaviors in (supported.get("features") or {}).items()
                           for behavior in behaviors}
    evidence_behaviors = {(item.get("feature"), item.get("behavior"))
                          for item in verified.get("behaviors") or []}
    evaluation_behaviors = {(item.get("feature_id"), behavior)
                            for item in task_results
                            for behavior in str(item.get("behavior_id") or "").split("|")
                            if behavior}
    trace_behaviors = {(item.get("feature_id"), behavior)
                       for item in task_results
                       if (item.get("golden_trace") or {}).get("feature")
                       for behavior in str(item.get("behavior_id") or "").split("|")
                       if behavior}
    holdout_behaviors = {(item.get("feature_id"), behavior)
                         for item in task_results if item.get("holdout")
                         for behavior in str(item.get("behavior_id") or "").split("|")
                         if behavior}

    def _listing(pairs) -> list:
        return sorted("%s/%s" % pair for pair in pairs)

    return {
        "supported": len(supported_behaviors),
        "evidence": len(evidence_behaviors),
        "evaluated": len(evaluation_behaviors),
        "golden_trace": len(trace_behaviors),
        "holdout": len(holdout_behaviors),
        "supported_without_evidence": _listing(supported_behaviors - evidence_behaviors),
        "evidence_without_task": _listing(evidence_behaviors - evaluation_behaviors),
        "task_without_evidence": _listing(evaluation_behaviors - evidence_behaviors),
        "holdout_without_task": _listing(holdout_behaviors - evaluation_behaviors),
    }


# ---------------------------------------------------------------- Phase 1.60：绑定对账

def binding_reconciliation(supported: dict, bindings_doc: dict | None,
                           scenarios: list | None = None) -> dict:
    """正式支持集 x 绑定库 的动态对账（任务书 §7）。

    支持集永远动态读取（supported_set()），不硬编码数量。返回：
    已绑定 / 未绑定 / 已审批绑定 / 未审批绑定、各场景 Trace 的绑定状态
    （SCENARIO_ONLY 不升级）、Baseline 覆盖与缺失。
    """
    supported_behaviors = {(feature, behavior)
                           for feature, behaviors in (supported.get("features") or {}).items()
                           for behavior in behaviors}
    bindings = list((bindings_doc or {}).get("bindings") or [])
    binding_pairs = {(str(item.get("feature_id")), str(item.get("behavior_id")))
                     for item in bindings}
    approved_pairs = {(str(item.get("feature_id")), str(item.get("behavior_id")))
                      for item in bindings if item.get("approved")}
    baseline_pairs = {(str(item.get("feature_id")), str(item.get("behavior_id")))
                      for item in bindings if item.get("baseline_id")}

    def _listing(pairs) -> list:
        return sorted("%s/%s" % pair for pair in pairs)

    trace_states = {}
    if trace_bindings is not None and scenarios:
        for scenario in scenarios:
            trace_states[str(scenario)] = trace_bindings.trace_binding_state(
                bindings, str(scenario))
    return {
        "supported_features": int(supported.get("feature_count") or 0),
        "supported_behaviors": len(supported_behaviors),
        "bound_behaviors": len(supported_behaviors & binding_pairs),
        "unbound_behaviors": len(supported_behaviors - binding_pairs),
        "unbound_listing": _listing(supported_behaviors - binding_pairs),
        "approved_bindings": len(approved_pairs),
        "unapproved_bindings": len(binding_pairs - approved_pairs),
        "baseline_backed_bindings": len(baseline_pairs),
        "contract_backed_bindings": len(binding_pairs - baseline_pairs),
        "bindings_outside_supported_set": _listing(binding_pairs - supported_behaviors),
        "trace_binding_states": trace_states,
    }
