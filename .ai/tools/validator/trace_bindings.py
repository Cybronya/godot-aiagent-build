#!/usr/bin/env python3
"""Trace / Behavior Binding（Phase 1.60）。

核心原则（任务书 §2）：

    场景级 Golden Trace ≠ 逐 Behavior Golden Trace。
    没有明确来源的 Expected，不是可信的评估依据。
    归属判定只用正式标识精确匹配，禁止子串/名称猜测。

Binding Schema（binding 文档：validator/bindings/behavior_bindings.json）：

    binding_id          绑定唯一标识
    feature_id          正式 Feature（Features/<id>/template.yaml#behavior）
    behavior_id         正式 Behavior（契约 `id`）
    scenario_id         关联编排场景（可空：契约级绑定没有场景 Trace）
    trace_id            行为级 Trace 引用（可空）
    trace_version       Trace 版本
    contract_version    Behavior Contract 版本（template.yaml#behavior 声明）
    baseline_id         关联 Baseline（可空）
    baseline_version    Baseline 版本
    expected            逐行为期望（check/target/entry/equals/count/... 形态，
                        与 evidence 任务 expect 同一比较语义）
    expected_source     behavior_contract | golden_trace | approved_baseline |
                        combined_approved
    expected_source_ref 来源凭据（契约路径 / 基线路径 / 组合声明的审批引用）
    approved            布尔；组合预期必须有 approval_reference
    approval_reference  审批凭据（自由文本 + 登记表引用）
    created_at/updated_at

Trace 绑定状态（任务书 §2.3）：

    SCENARIO_ONLY / BEHAVIOR_BOUND / BEHAVIOR_PARTIALLY_BOUND / UNBOUND

验证状态（任务书 §5，语义保留、命名可调）：

    VALID_BINDING / MISSING_BINDING / STALE_BINDING / INVALID_BINDING /
    REVOKED_BASELINE / UNAPPROVED_BASELINE / DIGEST_MISMATCH /
    CONTRACT_MISMATCH / SCENARIO_MISMATCH / NOT_APPLICABLE
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
VALIDATOR_DIR = _HERE
BINDINGS_PATH = os.path.join(_HERE, "bindings", "behavior_bindings.json")

SCHEMA = "behavior_trace_bindings"
SCHEMA_VERSION = 1

REQUIRED_FIELDS = ("binding_id", "feature_id", "behavior_id", "expected",
                   "expected_source")
EXPECTED_SOURCES = ("behavior_contract", "golden_trace", "approved_baseline",
                    "combined_approved")

# ---------------------------------------------------------------- 状态词表
SCENARIO_ONLY = "SCENARIO_ONLY"
BEHAVIOR_BOUND = "BEHAVIOR_BOUND"
BEHAVIOR_PARTIALLY_BOUND = "BEHAVIOR_PARTIALLY_BOUND"
UNBOUND = "UNBOUND"

VALID_BINDING = "VALID_BINDING"
MISSING_BINDING = "MISSING_BINDING"
STALE_BINDING = "STALE_BINDING"
INVALID_BINDING = "INVALID_BINDING"
REVOKED_BASELINE = "REVOKED_BASELINE"
UNAPPROVED_BASELINE = "UNAPPROVED_BASELINE"
DIGEST_MISMATCH = "DIGEST_MISMATCH"
CONTRACT_MISMATCH = "CONTRACT_MISMATCH"
SCENARIO_MISMATCH = "SCENARIO_MISMATCH"
NOT_APPLICABLE = "NOT_APPLICABLE"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- 绑定库

def load_bindings(path: str = "") -> dict:
    """读取绑定库（不存在 -> 空库；损坏 -> ValueError 由调用方处理）。"""
    target = path or BINDINGS_PATH
    if not os.path.isfile(target):
        return {"schema": SCHEMA, "schema_version": SCHEMA_VERSION, "bindings": []}
    with open(target, "r", encoding="utf-8") as handle:
        document = json.load(handle)
    validate_document(document, source=target)
    return document


def validate_document(document: dict, source: str = "") -> list:
    """Schema 校验：必填字段、来源词表、组合预期必须有审批凭据。"""
    if not isinstance(document, dict) or not isinstance(document.get("bindings"), list):
        raise ValueError("%s is not a behavior binding document" % source)
    problems: list = []
    seen_ids: set = set()
    seen_pairs: set = set()
    for index, binding in enumerate(document["bindings"]):
        where = "%sbindings[%d]" % (("%s: " % source) if source else "", index)
        if not isinstance(binding, dict):
            problems.append("%s is not an object" % where)
            continue
        for field in REQUIRED_FIELDS:
            if not binding.get(field):
                problems.append("%s missing required field %r" % (where, field))
        if binding.get("binding_id") in seen_ids:
            problems.append("%s duplicate binding_id %r" % (where, binding.get("binding_id")))
        seen_ids.add(binding.get("binding_id"))
        pair = (str(binding.get("feature_id")), str(binding.get("behavior_id")))
        if pair in seen_pairs:
            problems.append("%s duplicate feature/behavior binding %s/%s"
                            % (where, pair[0], pair[1]))
        seen_pairs.add(pair)
        if str(binding.get("expected_source")) not in EXPECTED_SOURCES:
            problems.append("%s unknown expected_source %r"
                            % (where, binding.get("expected_source")))
        if not isinstance(binding.get("expected"), list):
            problems.append("%s expected must be a list of expectation objects" % where)
        if binding.get("approved") and not binding.get("approval_reference"):
            problems.append("%s approved binding requires approval_reference" % where)
        if not binding.get("approved") and binding.get("approval_reference"):
            problems.append("%s approval_reference without approved=true" % where)
    return problems


def get_binding(document: dict, feature_id: str, behavior_id: str) -> dict | None:
    """精确 ID 匹配（不做任何子串/名称推断）。"""
    for binding in document.get("bindings") or []:
        if (str(binding.get("feature_id")) == str(feature_id)
                and str(binding.get("behavior_id")) == str(behavior_id)):
            return binding
    return None


def trace_binding_state(bindings: list, scenario_id: str) -> str:
    """一条场景级 Trace 的绑定状态（任务书 §2.3）。

    - 库里没有任何绑定引用该场景 -> SCENARIO_ONLY（保持 1.58 语义，不升级）。
    - 该场景下的绑定覆盖了全部声明行为 -> BEHAVIOR_BOUND。
    - 只覆盖一部分 -> BEHAVIOR_PARTIALLY_BOUND。
    - scenario_id 为空或库为空 -> UNBOUND。
    """
    if not scenario_id:
        return UNBOUND
    referencing = [binding for binding in bindings or []
                   if str(binding.get("scenario_id")) == str(scenario_id)]
    if not referencing:
        return SCENARIO_ONLY
    declared = {str(binding.get("behavior_id")) for binding in referencing}
    # 部分绑定判定需要「场景声明的行为全集」：绑定文档为同一场景的每条绑定
    # 记录 scenario_behavior_total（由生成方写入），缺省时无法证明全覆盖。
    totals = {int(binding.get("scenario_behavior_total") or 0) for binding in referencing}
    if totals and totals != {0}:
        total = totals.pop() if len(totals) == 1 else 0
        if total and len(declared) >= total:
            return BEHAVIOR_BOUND
        return BEHAVIOR_PARTIALLY_BOUND
    return BEHAVIOR_PARTIALLY_BOUND


# ---------------------------------------------------------------- 绑定验证

def validate_binding(binding: dict | None, *, feature_id: str, behavior_id: str,
                     scenario_id: str = "", contract_version: str = "",
                     contract_expected: list | None = None,
                     baseline_report: dict | None = None,
                     bindings: list | None = None) -> dict:
    """对单个 (Feature, Behavior) 做绑定验证。

    baseline_report 传 `baseline_lifecycle.use_baseline()` 的结果或
    `evidence_adapter.baseline_report()` 的结果（status/reason 已归一）。
    contract_expected 传当前契约的 expected 列表，用于校验绑定预期未被改宽。
    """
    result: dict = {"status": NOT_APPLICABLE, "reason": "", "binding_id": None,
                    "feature_id": feature_id, "behavior_id": behavior_id,
                    "scenario_id": scenario_id, "expected_source": None,
                    "approved": None, "contract_version": contract_version,
                    "expected_checks": 0}

    if binding is None:
        result["status"] = MISSING_BINDING
        result["reason"] = ("no binding for %s/%s; per-behavior expectation is not "
                            "trace-backed" % (feature_id, behavior_id))
        return result

    result.update({"binding_id": binding.get("binding_id"),
                   "expected_source": binding.get("expected_source"),
                   "approved": bool(binding.get("approved")),
                   "expected_checks": len(binding.get("expected") or [])})

    # 1) 身份必须精确一致（双保险：get_binding 已保证，防御直接构造的调用）
    if str(binding.get("feature_id")) != str(feature_id) or \
            str(binding.get("behavior_id")) != str(behavior_id):
        result["status"] = INVALID_BINDING
        result["reason"] = "binding identity does not match the declared ids"
        return result

    # 2) 绑定字段自身合法
    problems = validate_document({"bindings": [binding]})
    if problems:
        result["status"] = INVALID_BINDING
        result["reason"] = "; ".join(problems)
        return result

    # 3) 场景一致性：绑定声明了场景时必须与请求场景一致
    binding_scenario = str(binding.get("scenario_id") or "")
    if binding_scenario and scenario_id and binding_scenario != str(scenario_id):
        result["status"] = SCENARIO_MISMATCH
        result["reason"] = ("binding scenario %r != requested scenario %r"
                            % (binding_scenario, scenario_id))
        return result

    # 4) 契约版本一致性
    binding_contract = str(binding.get("contract_version") or "")
    if binding_contract and contract_version and binding_contract != str(contract_version):
        result["status"] = CONTRACT_MISMATCH
        result["reason"] = ("binding contract_version %r != current %r"
                            % (binding_contract, contract_version))
        return result

    # 5) 绑定预期不得比当前契约更宽（逐项必须能在契约 expected 中找到同键同值）。
    #    Phase 1.63 缺陷修复：契约索引按 (check, target, entry) 分组保留**列表**——
    #    同一目标的多条同类检查（如 node2d.displacement 的 x/y 轴）此前互相覆盖，
    #    导致最后一条顶掉前面的、误报「加宽契约」。匹配时额外核对 axis 等身份字段，
    #    并要求所有比较字段一致。
    if contract_expected is not None:
        contract_items: dict[tuple, list] = {}
        for item in contract_expected or []:
            if isinstance(item, dict):
                key = (str(item.get("check") or ""), str(item.get("target", ".")),
                       str(item.get("entry") or ""))
                contract_items.setdefault(key, []).append(item)
        identity_fields = ("axis",)
        compared_fields = ("equals", "count", "min", "max", "last_args")
        narrowed = []
        for expectation in binding.get("expected") or []:
            if not isinstance(expectation, dict):
                continue
            key = (str(expectation.get("check") or ""), str(expectation.get("target", ".")),
                   str(expectation.get("entry") or ""))
            items = contract_items.get(key)
            if not items:
                narrowed.append("%s@%s/%s not declared by the contract"
                                % (key[0], key[1], key[2]))
                continue
            identity = {f: expectation[f] for f in identity_fields if f in expectation}
            matched = False
            deviation = ""
            for contract_item in items:
                if any(contract_item.get(f) != value for f, value in identity.items()):
                    continue
                conflicts = ["%s=%r widens contract %r" % (field, expectation[field],
                                                           contract_item[field])
                             for field in compared_fields
                             if field in expectation and field in contract_item and
                             expectation[field] != contract_item[field]]
                if conflicts:
                    deviation = "; ".join(conflicts[:2])
                    continue
                missing = [field for field in compared_fields
                           if field in expectation and field not in contract_item]
                if missing:
                    deviation = ("%s not declared by the contract item" % missing[0])
                    continue
                matched = True
                break
            if not matched:
                narrowed.append("%s@%s/%s deviates from contract: %s"
                                % (key[0], key[1], key[2],
                                   deviation or "no consistent contract item"))
        if narrowed:
            result["status"] = CONTRACT_MISMATCH
            result["reason"] = "binding expected deviates from contract: " + "; ".join(narrowed[:3])
            return result

    # 6) Baseline 关联与信任
    if binding.get("baseline_id"):
        report = baseline_report or {}
        status = str(report.get("status") or "")
        lifecycle = str(report.get("lifecycle_status") or report.get("status") or "")
        if status in ("BASELINE_UNAPPROVED", "UNAPPROVED", "MISSING_REGISTRATION") or \
                lifecycle in ("UNAPPROVED", "MISSING_REGISTRATION", "REVOKED", "SUPERSEDED"):
            result["status"] = (REVOKED_BASELINE if lifecycle == "REVOKED"
                                else UNAPPROVED_BASELINE)
            result["reason"] = report.get("reason") or "baseline is not trusted"
            return result
        if status in ("INVALID_BASELINE",) or lifecycle == "DIGEST_MISMATCH" or \
                report.get("reason") == DIGEST_MISMATCH or status == DIGEST_MISMATCH:
            result["status"] = DIGEST_MISMATCH
            result["reason"] = report.get("reason") or "baseline digest mismatch"
            return result
        if status not in ("PASS", "APPROVED_OK"):
            result["status"] = STALE_BINDING
            result["reason"] = ("bound baseline is not usable: %s %s"
                                % (status, report.get("reason") or ""))
            return result

    result["status"] = VALID_BINDING
    result["reason"] = "binding is valid and its expectation sources are trusted"
    return result


def save_bindings(document: dict, path: str = "") -> None:
    """原子写回绑定库（写前校验，fail-closed）。"""
    problems = validate_document(document, source="save_bindings")
    if problems:
        raise ValueError("; ".join(problems[:3]))
    target = path or BINDINGS_PATH
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(tmp, target)
