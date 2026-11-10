#!/usr/bin/env python3
"""Provenance 签名封套 Schema 与规范化序列化（Phase 1.61）。

定位：**加法式**为信任链补上"由谁签发、签名是否适用于当前对象"的密码学证明层。
本模块只定义封套结构、规范化序列化与结果词表，不含任何密码学原语实现
（Ed25519 由 PyNaCl/libsodium 提供，见 signing.py）。

信任边界（必须如实声明，不得包装）：

    签名证明的是「持有某外部信任根所列私钥的主体，在时间 T 签署了摘要为
    D 的对象 O（用途 scope S）」。它**不**证明：
      - Godot 真的执行过对应行为（执行真实性需要独立采集器/可信执行环境）；
      - 采集进程未被篡改；
      - 签发者观察到的执行过程真实。
    若签名者与采集器同权限运行，其证明力等同采集器自报。

封套（detached signature envelope）：

    {
      "schema": "provenance_signature",
      "schema_version": 1,
      "object_type": "baseline" | "evidence_bundle" | "holdout_dataset",
      "object_id": "...",
      "object_version": "...",
      "content_digest": "<64-hex>",
      "digest_scheme": "<scheme id>",
      "scope": "approve_baseline" | "issue_evidence" | "seal_holdout",
      "signer_key_id": "PROVKEY-...",
      "signature_algorithm": "Ed25519",
      "signed_at": "ISO-8601 UTC",
      "binding": { 对象特定字段（例如审批者/审批时间/产物摘要集） },
      "signature": "<base64>"
    }

签名消息 = 封套去掉 signature 字段后的规范化 JSON 字节
（sort_keys + 紧凑分隔符 + UTF-8；与 baseline-content-digest-v1 的规范化
一致，字段顺序与无关空白不影响签名）。

对象类型 / ID / 版本 / 摘要 / scope 全部位于签名消息内，因此：

    - Baseline 签名不能用于 Evidence，反之亦然（跨对象类型复用失败）；
    - 一个对象的签名不能用于另一个对象（ID 复用失败）；
    - 不同版本之间不能无条件复用（版本复用失败）；
    - scope 不匹配即拒绝。

验证结果词表（fail-closed，语义互斥，不得混用）：

    SIGNATURE_VALID               验签通过（含密钥状态、授权、信任根信息）
    SIGNATURE_MISSING             没有签名封套
    SIGNATURE_INVALID             封套损坏 / 签名与消息不符 / 对象绑定不符
    KEY_UNKNOWN                   签名密钥不在外部信任根中
    KEY_REVOKED                   签名密钥已撤销（按撤销策略拒绝）
    SCOPE_MISMATCH                签名用途与对象类型不符，或密钥无此授权
    TRUST_ROOT_MISSING            外部信任根不存在
    TRUST_ROOT_UNREADABLE         外部信任根存在但损坏
    TRUST_ROOT_INSECURE_LOCATION  信任根路径位于项目工作区内（拒绝加载）
    ALGORITHM_MISMATCH            签名算法与密钥/封套声明不符
    LIBRARY_UNAVAILABLE           密码学库不可用（require 模式 fail-closed）
    DIGEST_MISMATCH               重算内容摘要与签名绑定的摘要不一致
"""

from __future__ import annotations

import json

SCHEMA = "provenance_signature"
SCHEMA_VERSION = 1

TRUST_ROOT_SCHEMA = "provenance_trust_root"
TRUST_ROOT_SCHEMA_VERSION = 1
REVOCATIONS_SCHEMA = "provenance_revocations"
REVOCATIONS_SCHEMA_VERSION = 1

ALGORITHM = "Ed25519"

# ---------------------------------------------------------------- 对象类型与 scope
OBJECT_BASELINE = "baseline"
OBJECT_EVIDENCE = "evidence_bundle"
OBJECT_HOLDOUT = "holdout_dataset"
OBJECT_ATTESTATION = "execution_attestation"  # Phase 1.62 新增
OBJECT_BINDING = "behavior_binding"           # Phase 1.63 新增
OBJECT_TYPES = (OBJECT_BASELINE, OBJECT_EVIDENCE, OBJECT_HOLDOUT, OBJECT_ATTESTATION,
                OBJECT_BINDING)

SCOPE_APPROVE_BASELINE = "approve_baseline"
SCOPE_ISSUE_EVIDENCE = "issue_evidence"
SCOPE_SEAL_HOLDOUT = "seal_holdout"
SCOPE_ATTEST_EXECUTION = "attest_execution"  # Phase 1.62 新增
SCOPE_APPROVE_BINDING = "approve_binding"    # Phase 1.63 新增

# 对象类型与签名用途的一一对应：跨用途复用签名在这里就被拒绝。
SCOPE_FOR_TYPE = {
    OBJECT_BASELINE: SCOPE_APPROVE_BASELINE,
    OBJECT_EVIDENCE: SCOPE_ISSUE_EVIDENCE,
    OBJECT_HOLDOUT: SCOPE_SEAL_HOLDOUT,
    OBJECT_ATTESTATION: SCOPE_ATTEST_EXECUTION,  # Phase 1.62 新增
    OBJECT_BINDING: SCOPE_APPROVE_BINDING,       # Phase 1.63 新增
}

SCOPES = (SCOPE_APPROVE_BASELINE, SCOPE_ISSUE_EVIDENCE, SCOPE_SEAL_HOLDOUT,
          SCOPE_ATTEST_EXECUTION,               # Phase 1.62 新增
          SCOPE_APPROVE_BINDING)                # Phase 1.63 新增

# ---------------------------------------------------------------- 结果词表
SIGNATURE_VALID = "SIGNATURE_VALID"
SIGNATURE_MISSING = "SIGNATURE_MISSING"
SIGNATURE_INVALID = "SIGNATURE_INVALID"
KEY_UNKNOWN = "KEY_UNKNOWN"
KEY_REVOKED = "KEY_REVOKED"
SCOPE_MISMATCH = "SCOPE_MISMATCH"
TRUST_ROOT_MISSING = "TRUST_ROOT_MISSING"
TRUST_ROOT_UNREADABLE = "TRUST_ROOT_UNREADABLE"
TRUST_ROOT_INSECURE_LOCATION = "TRUST_ROOT_INSECURE_LOCATION"
ALGORITHM_MISMATCH = "ALGORITHM_MISMATCH"
LIBRARY_UNAVAILABLE = "LIBRARY_UNAVAILABLE"
DIGEST_MISMATCH = "DIGEST_MISMATCH"

VERIFICATION_OUTCOMES = (
    SIGNATURE_VALID, SIGNATURE_MISSING, SIGNATURE_INVALID, KEY_UNKNOWN,
    KEY_REVOKED, SCOPE_MISMATCH, TRUST_ROOT_MISSING, TRUST_ROOT_UNREADABLE,
    TRUST_ROOT_INSECURE_LOCATION, ALGORITHM_MISMATCH, LIBRARY_UNAVAILABLE,
    DIGEST_MISMATCH,
)

# trust levels（对象可信等级，与生命周期状态正交）
TRUST_LEGACY_APPROVED = "LEGACY_APPROVED"
TRUST_CRYPTO_VERIFIED = "CRYPTOGRAPHICALLY_VERIFIED"
TRUST_SIGNATURE_REQUIRED = "SIGNATURE_REQUIRED"
TRUST_SIGNATURE_INVALID = "SIGNATURE_INVALID"
TRUST_LEVELS = (TRUST_LEGACY_APPROVED, TRUST_CRYPTO_VERIFIED,
                TRUST_SIGNATURE_REQUIRED, TRUST_SIGNATURE_INVALID)

ENVELOPE_REQUIRED_FIELDS = ("schema", "schema_version", "object_type",
                            "object_id", "object_version", "content_digest",
                            "digest_scheme", "scope", "signer_key_id",
                            "signature_algorithm", "signed_at", "signature")


def canonical(value) -> str:
    """确定性规范化 JSON：sort_keys + 紧凑分隔符 + UTF-8。

    与 baseline_lifecycle 的规范化一致：字段顺序与无关空白变化不影响签名；
    任何影响语义的内容变化必然改变签名消息。
    """
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def signed_message(envelope: dict) -> bytes:
    """签名消息：封套去掉 signature 字段后的规范化 JSON 字节。

    任何字段（含对象类型/ID/版本/摘要/scope/binding）改动都会改变消息，
    旧签名随即失效——这是跨对象复用被拒的机制基础。
    """
    message = {key: value for key, value in envelope.items()
               if key != "signature"}
    return canonical(message).encode("utf-8")


def envelope_summary(envelope: dict) -> dict:
    """封套的可报告摘要（不含签名与任何敏感材料，供日志/报告使用）。"""
    if not isinstance(envelope, dict):
        return {}
    return {key: envelope.get(key) for key in
            ("schema", "schema_version", "object_type", "object_id",
             "object_version", "content_digest", "digest_scheme", "scope",
             "signer_key_id", "signature_algorithm", "signed_at")}


def structure_errors(envelope, *, require_signature: bool = True) -> list:
    """封套结构校验（不含密码学验证）；返回人类可读错误列表。

    require_signature=False 用于**签发前**的未签名封套校验；
    验证侧一律 require_signature=True。
    """
    if not isinstance(envelope, dict):
        return ["signature envelope must be a JSON object"]
    errors = []
    required = ENVELOPE_REQUIRED_FIELDS if require_signature else \
        tuple(field for field in ENVELOPE_REQUIRED_FIELDS if field != "signature")
    for field in required:
        if field not in envelope:
            errors.append("envelope missing required field %r" % field)
    if envelope.get("schema") != SCHEMA:
        errors.append("unsupported envelope schema %r" % envelope.get("schema"))
    if envelope.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported envelope schema_version %r"
                      % envelope.get("schema_version"))
    if envelope.get("signature_algorithm") != ALGORITHM:
        errors.append("unsupported signature algorithm %r"
                      % envelope.get("signature_algorithm"))
    if envelope.get("object_type") not in OBJECT_TYPES:
        errors.append("unknown object_type %r" % envelope.get("object_type"))
    if envelope.get("scope") not in SCOPES:
        errors.append("unknown scope %r" % envelope.get("scope"))
    digest = envelope.get("content_digest")
    if not isinstance(digest, str) or len(digest) != 64:
        errors.append("content_digest must be a 64-char hex digest")
    if require_signature and (not isinstance(envelope.get("signature"), str)
                              or not envelope.get("signature")):
        errors.append("signature must be a non-empty base64 string")
    return errors
