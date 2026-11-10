#!/usr/bin/env python3
"""Provenance 验证管线（fail-closed）（Phase 1.61）。

验证顺序（每一步失败即返回对应结果，绝不继续）：

    1. 封套结构           -> SIGNATURE_INVALID
    2. 对象类型匹配       -> SIGNATURE_INVALID（跨类型复用，A07）
    3. scope 与类型一致   -> SCOPE_MISMATCH（A18）
    4. 对象 ID/版本匹配   -> SIGNATURE_INVALID（跨对象/跨版本复用，A08）
    5. 内容摘要匹配       -> DIGEST_MISMATCH（内容/摘要被改，A01/A02/A09/A11）
    6. 外部信任根可用     -> TRUST_ROOT_MISSING / UNREADABLE / INSECURE_LOCATION（A17/A16）
    7. 签名密钥在根中     -> KEY_UNKNOWN（A05）
    8. 算法一致           -> ALGORITHM_MISMATCH
    9. 密钥状态/撤销策略  -> KEY_REVOKED（A13；RETIRED 历史签名可验证）
   10. 密钥 scope 授权    -> SCOPE_MISMATCH（签名者授权不足）
   11. Ed25519 密码学验证 -> SIGNATURE_INVALID（A06）/ LIBRARY_UNAVAILABLE

全部通过 -> SIGNATURE_VALID（signer_subject 取自外部信任根，非自报）。

签名策略（signature_policy，任务书 §9）：

    allow_legacy  缺签名 -> LEGACY_APPROVED（历史数据不静默升级，
                  报告中如实标注）；**存在但无效的签名 -> 一律拒绝**。
    require_signature 缺签名 -> SIGNATURE_REQUIRED（拒绝）；无效 -> 拒绝。

Evidence sidecar：签名存放在 `<bundle>.sig.json`（bundle 文件本身零修改，
不破坏既有 bundle schema 与 payload_sha256 完整性）。
"""

from __future__ import annotations

import base64
import json
import os
import sys
from datetime import datetime, timezone

from . import signature_schema as schema
from .key_metadata import check_authorized
from .signing import load_nacl
from .trust_store import (STATUS_ACTIVE, STATUS_RETIRED, STATUS_REVOKED,
                          TrustStore, TrustStoreError)

POLICY_ALLOW_LEGACY = "allow_legacy"
POLICY_REQUIRE_SIGNATURE = "require_signature"
SIGNATURE_POLICIES = (POLICY_ALLOW_LEGACY, POLICY_REQUIRE_SIGNATURE)

SIDECAR_SUFFIX = ".sig.json"

REVOCATION_POLICY_REJECT = "reject"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _result(envelope: dict | None, status: str, reason: str = "",
            detail: str = "", *, trust: dict | None = None,
            key_record: dict | None = None) -> dict:
    result: dict = {
        "status": status,
        "reason": reason,
        "detail": detail,
        "verified_at": now_iso(),
    }
    summary = schema.envelope_summary(envelope or {})
    for field in ("object_type", "object_id", "object_version",
                  "content_digest", "digest_scheme", "scope",
                  "signer_key_id", "signature_algorithm", "signed_at"):
        result[field] = summary.get(field)
    if key_record is not None:
        result["signer_subject"] = key_record.get("subject")
        result["key_status"] = key_record.get("status")
    for field in ("trust_root_status", "trust_root_path", "trust_root_source"):
        result[field] = (trust or {}).get(field[len("trust_root_"):])
    return result


def _trust_fields(load: dict) -> dict:
    return {"trust_root_status": load.get("status"),
            "trust_root_path": load.get("path", ""),
            "trust_root_source": load.get("source_kind", "")}


def verify_envelope(envelope, *, object_type: str, object_id="",
                    object_version="", expected_digest: str = "",
                    expected_digest_scheme: str = "", trust_store: TrustStore,
                    revocation_policy: str = REVOCATION_POLICY_REJECT) -> dict:
    """验证一个签名封套是否适用于给定对象（fail-closed，见模块 docstring）。"""
    if not isinstance(envelope, dict):
        return _result(None, schema.SIGNATURE_MISSING,
                       "no signature envelope present")
    errors = schema.structure_errors(envelope)
    if errors:
        return _result(envelope, schema.SIGNATURE_INVALID,
                       "signature envelope is malformed",
                       "; ".join(errors))
    if str(envelope.get("object_type")) != str(object_type):
        return _result(envelope, schema.SIGNATURE_INVALID,
                       "signature was issued for object_type %r, not %r; "
                       "signatures cannot be reused across object types"
                       % (envelope.get("object_type"), object_type))
    expected_scope = schema.SCOPE_FOR_TYPE.get(str(object_type))
    if str(envelope.get("scope")) != str(expected_scope):
        return _result(envelope, schema.SCOPE_MISMATCH,
                       "signature scope %r does not match the required scope "
                       "%r for %s" % (envelope.get("scope"), expected_scope,
                                      object_type))
    # 对象身份/版本/摘要全部在签名消息内：任何不匹配都意味着这张签名
    # 不是为本对象/本版本/本内容签发的。
    if str(envelope.get("object_id")) != str(object_id):
        return _result(envelope, schema.SIGNATURE_INVALID,
                       "signature is bound to object %r, not %r"
                       % (envelope.get("object_id"), object_id))
    if str(envelope.get("object_version")) != str(object_version):
        return _result(envelope, schema.SIGNATURE_INVALID,
                       "signature is bound to version %r, not %r; versions "
                       "cannot silently reuse signatures"
                       % (envelope.get("object_version"), object_version))
    if expected_digest and str(envelope.get("content_digest")) != str(expected_digest):
        return _result(envelope, schema.DIGEST_MISMATCH,
                       "signed digest %s != recomputed content digest %s; the "
                       "signed content has been modified"
                       % (str(envelope.get("content_digest"))[:12],
                          str(expected_digest)[:12]))
    if expected_digest_scheme and \
            str(envelope.get("digest_scheme")) != str(expected_digest_scheme):
        return _result(envelope, schema.DIGEST_MISMATCH,
                       "signed digest scheme %r != expected %r"
                       % (envelope.get("digest_scheme"), expected_digest_scheme))

    # ---- 外部信任根（fail-closed：missing/unreadable/insecure 均拒绝）----
    load = trust_store.load()
    if not load["ok"]:
        return _result(envelope, load["status"], load["reason"],
                       load.get("detail", ""), trust=_trust_fields(load))
    key_record = None
    for record in load["keys"]:
        if str(record.get("key_id")) == str(envelope.get("signer_key_id")):
            key_record = record
            break
    if key_record is None:
        return _result(envelope, schema.KEY_UNKNOWN,
                       "signer key %r is not in the external trust root"
                       % envelope.get("signer_key_id"),
                       trust=_trust_fields(load))
    if str(key_record.get("algorithm")) != schema.ALGORITHM:
        return _result(envelope, schema.ALGORITHM_MISMATCH,
                       "trust root lists algorithm %r for %r"
                       % (key_record.get("algorithm"), key_record.get("key_id")),
                       trust=_trust_fields(load), key_record=key_record)
    key_status = str(key_record.get("status"))
    if key_status == STATUS_REVOKED:
        if revocation_policy != REVOCATION_POLICY_REJECT:
            return _result(envelope, schema.KEY_REVOKED,
                           "revocation policy %r is not implemented; refusing "
                           "(fail-closed)" % revocation_policy,
                           trust=_trust_fields(load), key_record=key_record)
        return _result(envelope, schema.KEY_REVOKED,
                       "signer key %r has been revoked; its signatures are "
                       "rejected under the %r policy"
                       % (key_record.get("key_id"), revocation_policy),
                       trust=_trust_fields(load), key_record=key_record)
    # RETIRED：历史签名可继续验证（轮换不改历史签名语义），结果中如实标注。
    ok, reason = check_authorized(key_record, str(envelope.get("scope")))
    if not ok:
        return _result(envelope, schema.SCOPE_MISMATCH, reason,
                       trust=_trust_fields(load), key_record=key_record)

    # ---- 密码学验证 ----
    module, error = load_nacl()
    if module is None:
        return _result(envelope, schema.LIBRARY_UNAVAILABLE, error,
                       trust=_trust_fields(load), key_record=key_record)
    try:
        signature = base64.b64decode(str(envelope.get("signature")),
                                     validate=True)
    except (ValueError, TypeError):
        return _result(envelope, schema.SIGNATURE_INVALID,
                       "signature field is not valid base64",
                       trust=_trust_fields(load), key_record=key_record)
    verify_key = module.VerifyKey(base64.b64decode(str(key_record.get("public_key"))))
    try:
        verify_key.verify(schema.signed_message(envelope), signature)
    except Exception:  # noqa: BLE001 - nacl.exceptions.BadSignatureError 及任何库异常
        return _result(envelope, schema.SIGNATURE_INVALID,
                       "Ed25519 verification failed: the signature does not "
                       "match the message under the trusted public key %r"
                       % key_record.get("key_id"),
                       trust=_trust_fields(load), key_record=key_record)
    result = _result(envelope, schema.SIGNATURE_VALID,
                     "signature valid; signer identity and authorization come "
                     "from the external trust root",
                     trust=_trust_fields(load), key_record=key_record)
    result["note"] = ("signature proves who signed the digest, not that the "
                      "recorded execution actually happened")
    return result


# ---------------------------------------------------------------- 策略封装

def evaluate_signature(envelope, *, object_type: str, object_id="",
                       object_version="", expected_digest: str = "",
                       expected_digest_scheme: str = "",
                       trust_store: TrustStore,
                       signature_policy: str = POLICY_ALLOW_LEGACY) -> dict:
    """按签名策略给出对象的可信等级（trust_level）与验证明细。

    返回 {trust_level, usable, verification{...}}：

        trust_level = LEGACY_APPROVED            缺签名且 allow_legacy（不阻断，
                                                 但绝不冒充"已验证"）
        trust_level = CRYPTOGRAPHICALLY_VERIFIED 验签通过
        trust_level = SIGNATURE_REQUIRED         缺签名且 require（不可用）
        trust_level = SIGNATURE_INVALID          签名存在但无效/密钥不可信/
                                                 信任根问题（一律不可用，
                                                 即使 allow_legacy——
                                                 "带病签名"不能当 Legacy 放行）
    """
    if signature_policy not in SIGNATURE_POLICIES:
        return {"trust_level": schema.TRUST_SIGNATURE_INVALID, "usable": False,
                "verification": {"status": schema.SIGNATURE_INVALID,
                                 "reason": "unknown signature policy %r"
                                           % signature_policy}}
    if not isinstance(envelope, dict):
        # 没有签名：按策略区分 Legacy / Required。
        if signature_policy == POLICY_REQUIRE_SIGNATURE:
            return {"trust_level": schema.TRUST_SIGNATURE_REQUIRED,
                    "usable": False,
                    "verification": {
                        "status": schema.SIGNATURE_MISSING,
                        "reason": "signature required by policy but no "
                                  "signature envelope is present"}}
        return {"trust_level": schema.TRUST_LEGACY_APPROVED, "usable": True,
                "verification": {
                    "status": schema.SIGNATURE_MISSING,
                    "reason": "no signature envelope; object remains "
                              "LEGACY_APPROVED and is never reported as "
                              "cryptographically verified"}}
    verification = verify_envelope(envelope, object_type=object_type,
                                   object_id=object_id,
                                   object_version=object_version,
                                   expected_digest=expected_digest,
                                   expected_digest_scheme=expected_digest_scheme,
                                   trust_store=trust_store)
    if verification["status"] == schema.SIGNATURE_VALID:
        return {"trust_level": schema.TRUST_CRYPTO_VERIFIED, "usable": True,
                "verification": verification}
    return {"trust_level": schema.TRUST_SIGNATURE_INVALID, "usable": False,
            "verification": verification}


# ---------------------------------------------------------------- Evidence sidecar

def recompute_evidence_digest(document: dict) -> str:
    """重算 Evidence Bundle 内容摘要（复用采集器的 canonical 实现，不复制规则）。

    与 check_behavior_evidence.verify_integrity 的重算口径一致：
    canonical(整个 bundle，除 integrity 字段) 的 SHA256。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    scene_composer = os.path.join(os.path.dirname(os.path.dirname(here)),
                                  "scene_composer")
    if scene_composer not in sys.path:
        sys.path.insert(0, scene_composer)
    import feature_behavior_evidence as fbe  # noqa: PLC0415 - 延迟导入
    return fbe.bundle_digest(document)


def sidecar_path(bundle_path: str) -> str:
    return str(bundle_path) + SIDECAR_SUFFIX


def load_sidecar(bundle_path: str) -> tuple[dict | None, list]:
    """读取 Evidence sidecar 签名；不存在返回 (None, [])。"""
    target = sidecar_path(bundle_path)
    if not os.path.isfile(target):
        return None, []
    try:
        with open(target, "r", encoding="utf-8") as handle:
            envelope = json.load(handle)
    except (OSError, ValueError) as exc:
        return None, ["sidecar unreadable: %s" % exc.__class__.__name__]
    if not isinstance(envelope, dict):
        return None, ["sidecar must be a JSON object"]
    return envelope, []


def write_sidecar(bundle_path: str, envelope: dict) -> str:
    """把封套写入 sidecar（bundle 文件字节零改动）。"""
    target = sidecar_path(bundle_path)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(envelope, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(tmp, target)
    return target


def verify_evidence_bundle(bundle_path: str, document: dict, *,
                           trust_store: TrustStore,
                           signature_policy: str = POLICY_ALLOW_LEGACY,
                           recomputed_digest: str = "") -> dict:
    """Evidence Bundle 来源验证：重算摘要 -> 验证 sidecar 封套 -> 策略分级。

    recomputed_digest 为空时自动重算（调用方也可以传入自己重算的值，
    例如 adapter 复用 verify_integrity 的口径）。
    """
    try:
        digest = recomputed_digest or recompute_evidence_digest(document)
    except Exception as exc:  # noqa: BLE001 - 摘要失败绝不放行
        return {"trust_level": schema.TRUST_SIGNATURE_INVALID, "usable": False,
                "verification": {"status": schema.DIGEST_MISMATCH,
                                 "reason": "evidence digest recomputation failed",
                                 "detail": str(exc)}}
    envelope, errors = load_sidecar(bundle_path)
    if errors:
        return {"trust_level": schema.TRUST_SIGNATURE_INVALID, "usable": False,
                "verification": {"status": schema.SIGNATURE_INVALID,
                                 "reason": errors[0]}}
    evaluated = evaluate_signature(
        envelope, object_type=schema.OBJECT_EVIDENCE,
        object_id=str(document.get("bundle_id") or ""),
        object_version=str(document.get("schema_version") or ""),
        expected_digest=digest,
        expected_digest_scheme="evidence-bundle-digest-v1",
        trust_store=trust_store, signature_policy=signature_policy)
    evaluated["content_digest"] = digest
    return evaluated
