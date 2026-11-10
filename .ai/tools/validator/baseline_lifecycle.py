#!/usr/bin/env python3
"""Baseline 生命周期与内容完整性（Phase 1.60）。

定位：**加法式**完善 Golden Trace Baseline 的可信链路，不重写现有审批入口
（`e2e/approve_trace_baselines.py`）、不重录任何基线、不改 `trace_baselines.py`
的比较语义。

关闭的缺口（Phase 1.60 审计 §3.3/§3.4）：

    审批后修改基线内容（保留合法的 approval 块）可以逃过 `baseline_report()`
    的结构校验 —— 因为使用时不重算内容摘要。

交付的能力（与任务书 §10 对应）：

    A. 内容完整性：规范化 SHA256 内容摘要 + 使用时重算比对。
    B. 审批流程完整性：显式状态机 + 审批登记表（baseline_id/version/digest/
       审批依据），使用时核对登记记录。
    C. 审批者身份真实性：**不提供**。approver 是自报文本，登记表与基线同权限
       可写；同权限攻击者仍可同时改写内容、摘要与登记。独立签名与外部信任根
       属于后续阶段，本模块的输出不得被描述为防篡改签名。

生命周期状态（任务书 §3.1）：

    DRAFT -> PENDING_REVIEW -> APPROVED
    PENDING_REVIEW -> REJECTED
    APPROVED -> SUPERSEDED（被更新版本替代）
    APPROVED -> REVOKED（撤销）

硬规则：

    - DRAFT / PENDING_REVIEW / REJECTED / REVOKED / SUPERSEDed 不得用于正式评估。
    - 内容摘要与审批登记不一致 -> 旧审批失效，必须重新登记（重新走审批）。
    - 自报 `approved=true` 不能绕过登记核对。
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
VALIDATOR_DIR = _HERE
BASELINES_DIR = os.path.join(_HERE, "baselines")
REGISTRY_PATH = os.path.join(BASELINES_DIR, "approval_registry.json")

SCHEMA = "baseline_approval_registry"
SCHEMA_VERSION = 1

# 规范化摘要方案版本：任何字段集变化必须升版（旧登记随之 DIGEST_MISMATCH）
DIGEST_SCHEME = "baseline-content-digest-v1"

# ---------------------------------------------------------------- 生命周期
DRAFT = "DRAFT"
PENDING_REVIEW = "PENDING_REVIEW"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
SUPERSEDED = "SUPERSEDED"
REVOKED = "REVOKED"

LIFECYCLE_STATES = (DRAFT, PENDING_REVIEW, APPROVED, REJECTED, SUPERSEDED, REVOKED)

# 允许的正式评估状态：只有 APPROVED
USABLE_STATES = (APPROVED,)

# 合法状态转换（审批入口只负责 APPROVED 的登记；其余转换由运维操作写登记表，
# 但转换本身在这里被校验，不允许跳步）
LEGAL_TRANSITIONS = {
    DRAFT: {PENDING_REVIEW, REJECTED},
    PENDING_REVIEW: {APPROVED, REJECTED},
    APPROVED: {SUPERSEDED, REVOKED},
    REJECTED: {DRAFT},
    SUPERSEDED: set(),
    REVOKED: set(),
}


class LifecycleError(ValueError):
    """登记表操作非法（非法转换 / 字段缺失 / 摘要缺失）。"""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- 内容摘要

def _canonical(value) -> str:
    """规范化 JSON 序列化：sort_keys + 紧凑分隔符 + UTF-8。

    目标：字段顺序与无关空白变化不改变摘要；任何影响评估语义的内容变化
    必然改变摘要。
    """
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def evaluation_payload(document: dict) -> dict:
    """抽取**参与评估**的载荷字段（摘要覆盖范围）。

    明确排除：
        approval            审批元数据（含合法追加的 coverage 修订说明、
                            fingerprint scheme 演进），不是比较语义的一部分；
                            内容篡改由"摘要与登记比对"在**登记内**捕获——
                            改内容必改 payload，改 approval 不改 payload。
        scenario_description 纯说明文字，不参与比较。
    其余全部字段（events / comparison_policy / expected_final_state /
    scenario_id / 各 schema 版本 / approved_behavior_version / coverage /
    source / document 等）都参与摘要。
    """
    return {key: value for key, value in document.items()
            if key not in ("approval", "scenario_description")}


def content_digest(document: dict, scheme: str = DIGEST_SCHEME) -> dict:
    """计算基线内容摘要（带方案标识，避免静默换算法）。"""
    if scheme != DIGEST_SCHEME:
        raise LifecycleError("unknown digest scheme %r" % scheme)
    payload = evaluation_payload(document)
    digest = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
    return {"scheme": DIGEST_SCHEME, "digest": digest}


# ---------------------------------------------------------------- 登记表

def _load_registry(path: str = "") -> dict:
    target = path or REGISTRY_PATH
    if not os.path.isfile(target):
        return {"schema": SCHEMA, "schema_version": SCHEMA_VERSION,
                "registrations": []}
    with open(target, "r", encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict) or not isinstance(document.get("registrations"), list):
        raise LifecycleError("approval registry %s is malformed" % target)
    return document


def _save_registry(registry: dict, path: str = "") -> None:
    target = path or REGISTRY_PATH
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(registry, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(tmp, target)


def _find(registry: dict, baseline_id: str, baseline_version) -> dict | None:
    for entry in registry.get("registrations") or []:
        if (str(entry.get("baseline_id")) == str(baseline_id)
                and str(entry.get("baseline_version")) == str(baseline_version)):
            return entry
    return None


def register(baseline_id: str, baseline_version, status: str, *,
             content: dict | None = None, digest: str = "",
             approver: str = "", approved_at: str = "", basis: str = "",
             previous_status: str = "", registry_path: str = "",
             registered_at: str = "", approval_reference: str = "",
             approval_fingerprint: str = "") -> dict:
    """登记/更新一条基线记录（带状态机与摘要校验，fail-closed）。

    - 新登记必须带 digest（或 content 供即时计算）与 basis（登记依据）。
    - 状态转换必须合法；不填 previous_status 表示新登记（只允许非终态起点）。
    """
    if status not in LIFECYCLE_STATES:
        raise LifecycleError("unknown lifecycle status %r" % status)
    if not digest and content is not None:
        digest = content_digest(content)["digest"]
    if not digest:
        raise LifecycleError("registration requires a content digest")
    if not basis:
        raise LifecycleError("registration requires a basis (approval reference)")

    registry = _load_registry(registry_path)
    existing = _find(registry, baseline_id, baseline_version)
    if existing is not None and previous_status:
        if str(existing.get("status")) != previous_status:
            raise LifecycleError(
                "transition %s->%s rejected: registry says %s"
                % (previous_status, status, existing.get("status")))
        if previous_status not in LEGAL_TRANSITIONS or \
                status not in LEGAL_TRANSITIONS[previous_status]:
            raise LifecycleError("illegal lifecycle transition %s -> %s"
                                 % (previous_status, status))
    elif existing is not None and not previous_status:
        # 同键重复登记：视为更新（例如 digest 复核后重批），但必须显式带
        # previous_status，否则拒绝 —— 防止悄悄覆盖一条 REVOKED 记录。
        raise LifecycleError(
            "baseline %s v%s already registered (status=%s); pass previous_status "
            "to record an explicit transition"
            % (baseline_id, baseline_version, existing.get("status")))

    record = {
        "baseline_id": str(baseline_id),
        "baseline_version": str(baseline_version),
        "status": status,
        "content_digest": digest,
        "digest_scheme": DIGEST_SCHEME,
        "approver": str(approver),
        "approved_at": str(approved_at),
        "approval_fingerprint": str(approval_fingerprint or ""),
        "basis": str(basis),
        "approval_reference": str(approval_reference),
        "registered_at": registered_at or now_iso(),
    }
    if existing is not None:
        registry["registrations"][registry["registrations"].index(existing)] = record
    else:
        registry["registrations"].append(record)
    _save_registry(registry, registry_path)
    return record


# ---------------------------------------------------------------- 使用时复核

def use_baseline(document: dict, *, baseline_path: str = "",
                 registry_path: str = "") -> dict:
    """使用时复核：结构合法 + 文件内审批 + 登记存在 + 状态可用 + 摘要一致。

    返回（不抛异常，调用方按 status 决策）：

        APPROVED_OK          可用
        DIGEST_MISMATCH      内容与审批登记不一致（旧审批失效）
        UNAPPROVED           文件内 approval.status != approved
        REVOKED / SUPERSEDED 登记状态禁止使用
        MISSING_REGISTRATION 没有登记记录（含旧数据未迁移）
        INVALID_BASELINE     结构非法 / 不可读 / 登记表损坏
    """
    import trace_baselines  # 延迟导入：避免测试环境无依赖时拖垮整个模块
    result: dict = {
        "status": "INVALID_BASELINE", "reason": "", "detail": "",
        "baseline_id": document.get("scenario_id") if isinstance(document, dict) else None,
        "baseline_version": document.get("baseline_version") if isinstance(document, dict) else None,
        "content_digest": None, "digest_scheme": DIGEST_SCHEME,
        "lifecycle_status": None, "registered_digest": None,
        "baseline_path": baseline_path,
    }
    if not isinstance(document, dict):
        result["reason"] = "baseline document is not an object"
        return result
    try:
        computed = content_digest(document)
    except (TypeError, ValueError) as exc:
        result["reason"] = "digest computation failed"
        result["detail"] = str(exc)
        return result
    result["content_digest"] = computed["digest"]

    approval = document.get("approval") or {}
    if str(approval.get("status")) != "approved":
        result["status"] = "UNAPPROVED"
        result["reason"] = ("baseline approval status is %r (must be 'approved')"
                            % approval.get("status"))
        return result

    try:
        registry = _load_registry(registry_path)
    except (OSError, ValueError, LifecycleError) as exc:
        result["reason"] = "approval registry unreadable"
        result["detail"] = str(exc)
        return result
    entry = _find(registry, result["baseline_id"], result["baseline_version"])
    if entry is None:
        result["status"] = "MISSING_REGISTRATION"
        result["reason"] = ("no approval registry entry for %s v%s; baseline must be "
                            "registered (with its content digest) before use"
                            % (result["baseline_id"], result["baseline_version"]))
        return result
    result["lifecycle_status"] = entry.get("status")
    result["registered_digest"] = entry.get("content_digest")
    if entry.get("status") not in USABLE_STATES:
        result["status"] = entry.get("status")
        result["reason"] = "baseline lifecycle status is %r (not usable)" % entry.get("status")
        return result
    if str(entry.get("content_digest")) != computed["digest"]:
        result["status"] = "DIGEST_MISMATCH"
        result["reason"] = ("baseline content changed after approval: registry digest "
                            "%s != computed %s; old approval is void"
                            % (str(entry.get("content_digest"))[:12],
                               computed["digest"][:12]))
        return result
    # 审批块一致性：payload 摘要不覆盖 approval（合法的 coverage 修订先例），
    # 因此单独核对登记时固化的审批者 / 审批时间 / 指纹——重写 approval 块
    # （伪造审批者）不能通过使用时复核。
    approval = document.get("approval") or {}
    for field in ("approver", "approved_at"):
        registered = str(entry.get(field) or "")
        if registered and str(approval.get(field) or "") != registered:
            result["status"] = "APPROVAL_MISMATCH"
            result["reason"] = ("in-file approval.%s %r does not match the registered "
                                "approval %r; re-approval is required"
                                % (field, approval.get(field), registered))
            return result
    registered_fingerprint = str(entry.get("approval_fingerprint") or "")
    if registered_fingerprint and \
            str(approval.get("candidate_fingerprint") or "") != registered_fingerprint:
        result["status"] = "APPROVAL_MISMATCH"
        result["reason"] = "in-file approval.candidate_fingerprint does not match the registration"
        return result
    result["status"] = "APPROVED_OK"
    result["reason"] = "approved, registered and digest verified"
    return result


def migrate_existing_baseline(path: str, *, basis: str, approver: str = "",
                              approved_at: str = "", registry_path: str = "") -> dict:
    """把一条**既有已批准**基线显式登记入表（不是自动审批）。

    条件：文件内 approval.status == approved 且 trace_baselines.validate_baseline()
    无错误。登记依据（basis）必须写明迁移来源；摘要在登记时一次性固定，
    之后任何内容变化都会在使用时被 DIGEST_MISMATCH 拒绝。
    """
    import trace_baselines
    with open(path, "r", encoding="utf-8") as handle:
        document = json.load(handle)
    errors = trace_baselines.validate_baseline(document)
    if errors:
        raise LifecycleError("baseline %s is not structurally valid: %s"
                             % (path, "; ".join(str(item) for item in errors[:3])))
    approval = document.get("approval") or {}
    if str(approval.get("status")) != "approved":
        raise LifecycleError("baseline %s is not approved in-file" % path)
    computed = content_digest(document)
    record = register(
        document.get("scenario_id"), document.get("baseline_version"), APPROVED,
        digest=computed["digest"],
        approver=approver or str(approval.get("approver") or ""),
        approved_at=approved_at or str(approval.get("approved_at") or ""),
        basis=basis,
        approval_fingerprint=str(approval.get("candidate_fingerprint") or ""),
        approval_reference="in-file approval block: approver=%s approved_at=%s "
                           "fingerprint=%s" % (approval.get("approver"),
                                               approval.get("approved_at"),
                                               str(approval.get("candidate_fingerprint"))[:16]),
        registry_path=registry_path)
    return record


# ---------------------------------------------------------------- Phase 1.61 来源签名

# 信任等级（与生命周期状态正交，不得混用）：
#   LEGACY_APPROVED            历史登记，无签名 —— 不伪造、不自动升级
#   CRYPTOGRAPHICALLY_VERIFIED 外部信任根验签通过
#   SIGNATURE_REQUIRED         require 模式下缺签名（不可用）
#   SIGNATURE_INVALID          签名存在但无效/密钥不可信（一律不可用，
#                              即使 allow-legacy 模式 —— "带病签名"不能当 Legacy 放行）

def use_baseline_trusted(document: dict, *, baseline_path: str = "",
                         registry_path: str = "",
                         trust_store=None,
                         signature_policy: str = "allow_legacy") -> dict:
    """Phase 1.61：在 use_baseline 之上叠加来源签名验证（加法式）。

    - 登记条目中的可选 `provenance_signature` 封套绑定：baseline_id / version /
      内容摘要（登记时固化的 content_digest）/ 审批者 / 审批时间 / scope
      = approve_baseline；公钥来自外部信任根（工作区之外）。
    - 无签名 + allow_legacy → LEGACY_APPROVED（可用，但报告中如实标注，
      绝不冒充 CRYPTOGRAPHICALLY_VERIFIED）。
    - 无签名 + require_signature → SIGNATURE_REQUIRED（不可用）。
    - 签名存在但无效（含密钥未知/撤销/信任根缺失/摘要不符）→
      SIGNATURE_INVALID（**任何模式都不可用**）。
    - 1.60 的全部语义先于签名验证执行：任何 use_baseline 失败原样返回。

    返回在 use_baseline 结果上追加：provenance_trust（信任等级）、
    provenance（验证明细，无签名时为策略说明）。
    """
    result = use_baseline(document, baseline_path=baseline_path,
                          registry_path=registry_path)
    entry = None
    if result.get("status") == "APPROVED_OK" and registry_path is not None:
        try:
            registry = _load_registry(registry_path)
            entry = _find(registry, result.get("baseline_id"),
                          result.get("baseline_version"))
        except (OSError, ValueError, LifecycleError):
            entry = None
    provenance: dict = {"policy": signature_policy}
    if result.get("status") != "APPROVED_OK":
        # 生命周期/摘要/登记问题优先：签名验证不做二次裁决。
        provenance["trust_level"] = "NOT_EVALUATED"
        provenance["reason"] = ("lifecycle check returned %s; provenance not "
                               "evaluated" % result.get("status"))
        result["provenance"] = provenance
        result["provenance_trust"] = provenance["trust_level"]
        return result
    if entry is None:  # 理论上不会发生（APPROVED_OK 必有登记）
        provenance["trust_level"] = "NOT_EVALUATED"
        provenance["reason"] = "registry entry unavailable"
        result["provenance"] = provenance
        result["provenance_trust"] = provenance["trust_level"]
        return result
    envelope = entry.get("provenance_signature")
    try:
        from provenance import verification as provenance_verification
    except ImportError:  # noqa: F841 - provenance 包不可用时按缺签名处理
        provenance_verification = None
    if provenance_verification is None:
        if envelope is None:
            provenance["trust_level"] = ("SIGNATURE_REQUIRED"
                                         if signature_policy == "require_signature"
                                         else "LEGACY_APPROVED")
            provenance["reason"] = ("provenance module unavailable; treating as "
                                    "%s" % provenance["trust_level"])
            result["provenance"] = provenance
            result["provenance_trust"] = provenance["trust_level"]
            if signature_policy == "require_signature":
                result["status"] = "SIGNATURE_REQUIRED"
                result["reason"] = provenance["reason"]
            return result
        # 有签名但验不了：fail-closed（绝不把带签对象当 Legacy 放行）
        provenance["trust_level"] = "SIGNATURE_INVALID"
        provenance["reason"] = "provenance module unavailable; signature cannot be verified"
        result["provenance"] = provenance
        result["provenance_trust"] = provenance["trust_level"]
        result["status"] = "SIGNATURE_INVALID"
        result["reason"] = provenance["reason"]
        return result

    evaluated = provenance_verification.evaluate_signature(
        envelope, object_type="baseline",
        object_id=result.get("baseline_id"),
        object_version=result.get("baseline_version"),
        # 摘要用**登记表里固化**的摘要：签名证明的是"审批时看到的那个内容"。
        expected_digest=str(entry.get("content_digest") or ""),
        expected_digest_scheme=str(entry.get("digest_scheme")
                                   or DIGEST_SCHEME),
        trust_store=trust_store, signature_policy=signature_policy)
    # 审批元数据交叉核对：签名内的 approver / approved_at 必须与登记记录一致。
    # 改登记审批者（A03）而保留签名 → 签名验证失败（不只是 APPROVAL_MISMATCH）。
    if evaluated["usable"]:
        binding = dict((envelope or {}).get("binding") or {})
        for field in ("approver", "approved_at"):
            signed_value = str(binding.get(field) or "")
            if signed_value and str(entry.get(field) or "") != signed_value:
                evaluated = {"trust_level": "SIGNATURE_INVALID", "usable": False,
                             "verification": {
                                 "status": "SIGNATURE_INVALID",
                                 "reason": ("registered %s %r does not match the "
                                            "signed approval %r; the approval "
                                            "registry was modified after signing"
                                            % (field, entry.get(field), signed_value))}}
                break
    provenance["trust_level"] = evaluated["trust_level"]
    provenance["usable"] = evaluated["usable"]
    provenance["verification"] = evaluated["verification"]
    provenance["signer_subject"] = (evaluated["verification"] or {}).get(
        "signer_subject")
    if not evaluated["usable"]:
        result["status"] = ("SIGNATURE_REQUIRED"
                            if evaluated["trust_level"] == "SIGNATURE_REQUIRED"
                            else "SIGNATURE_INVALID")
        result["reason"] = (evaluated["verification"] or {}).get("reason") or \
                           ("baseline provenance trust level is %r (not usable)"
                            % evaluated["trust_level"])
    result["provenance"] = provenance
    result["provenance_trust"] = evaluated["trust_level"]
    return result
