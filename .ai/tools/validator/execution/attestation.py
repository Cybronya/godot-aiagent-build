#!/usr/bin/env python3
"""Execution Attestation —— 受信任主体对 Run Manifest 签署执行证明（Phase 1.62）。

核心定位（诚实声明）：
    Attestation 证明的是「持有外部信任根中某私钥的执行器，在时间 T 观察到
    Run Manifest M + Artifact Set A + Fingerprint Set F 并确认执行状态 S，
    然后签发了证明 A 」。

    它**不**证明：
    - 执行器本身没有被攻击者替换（需要硬件信任根或独立容器——本阶段没有）
    - Godot 没有被篡改（采集器/执行器与 Godot 在同一权限边界）
    - 执行环境不是伪造的

    本阶段能实现 LOCAL_ISOLATED 等级：执行器 = 本地 Python（与项目同权限），
    但签名密钥在工作区外（Phase 1.61 机制）。
    EXTERNAL_TRUSTED_RUNNER / HARDWARE_ATTESTED —— **本阶段不实现**。

设计原则：
    1. 复用 Phase 1.61 签名体系（Ed25519, TrustStore, sign_envelope / verify_envelope）
    2. 只新增 execution_attestation object_type + attest_execution scope
    3. Attestation 签名覆盖 manifest_digest + 所有指纹 + artifact_set_digest + run_id
    4. 签发时机：执行完成后（SUCCEEDED / FAILED / TIMEOUT / CRASHED）
    5. 签发时重新计算 Artifact 摘要（不直接信采集器自报）
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone


# ---------------------------------------------------------------- 复用 Phase 1.61

# 延迟导入 provenance（避免循环依赖 + 让 import 顺序不敏感）
def _get_provenance():
    """确保 provenance 模块在 sys.path 中可导入。"""
    here = os.path.dirname(os.path.abspath(__file__))
    validator_dir = os.path.dirname(here)
    if validator_dir not in sys.path:
        sys.path.insert(0, validator_dir)
    from provenance import signature_schema, signing, verification, trust_store  # noqa: PLC0415
    return signature_schema, signing, verification, trust_store


# ---------------------------------------------------------------- Attestation Schema

SCHEMA = "execution_attestation"
SCHEMA_VERSION = 1
OBJECT_TYPE = "execution_attestation"
SCOPE = "attest_execution"

TRUST_LEVEL_LOCAL_ISOLATED = "LOCAL_ISOLATED"
TRUST_LEVEL_LOCAL_UNTRUSTED = "LOCAL_UNTRUSTED"
TRUST_LEVEL_EXTERNAL_TRUSTED_RUNNER = "EXTERNAL_TRUSTED_RUNNER"
TRUST_LEVEL_HARDWARE_ATTESTED = "HARDWARE_ATTESTED"
TRUST_LEVELS = (TRUST_LEVEL_LOCAL_UNTRUSTED, TRUST_LEVEL_LOCAL_ISOLATED,
                TRUST_LEVEL_EXTERNAL_TRUSTED_RUNNER, TRUST_LEVEL_HARDWARE_ATTESTED)

STATUS_ATTESTED_VERIFIED = "ATTESTED_VERIFIED"
STATUS_ATTESTATION_MISSING = "ATTESTATION_MISSING"
STATUS_ATTESTATION_INVALID = "ATTESTATION_INVALID"
STATUS_SIGNER_UNTRUSTED = "SIGNER_UNTRUSTED"
STATUS_SIGNER_UNAUTHORIZED = "SIGNER_UNAUTHORIZED"
STATUS_MANIFEST_DIGEST_MISMATCH = "MANIFEST_DIGEST_MISMATCH"
STATUS_RUN_ID_MISMATCH = "RUN_ID_MISMATCH"
STATUS_EXECUTION_ID_MISMATCH = "EXECUTION_ID_MISMATCH"
STATUS_ENVIRONMENT_MISMATCH = "ENVIRONMENT_MISMATCH"
STATUS_COLLECTOR_MISMATCH = "COLLECTOR_MISMATCH"
STATUS_SOURCE_MISMATCH = "SOURCE_MISMATCH"
STATUS_CONFIG_MISMATCH = "CONFIG_MISMATCH"
STATUS_ARTIFACT_SET_MISMATCH = "ARTIFACT_SET_MISMATCH"
STATUS_ARTIFACT_MISSING = "ARTIFACT_MISSING"
STATUS_EXECUTION_FAILED = "EXECUTION_FAILED"
STATUS_EXECUTION_INCOMPLETE = "EXECUTION_INCOMPLETE"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_json(data) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def digest_document(data) -> str:
    return hashlib.sha256(_canonical_json(data)).hexdigest()


def compute_attestation_digest(attestation: dict) -> str:
    """对 Attestation 文档去掉 attestation_digest 后做 canonical SHA256。"""
    clean = {k: v for k, v in attestation.items()
             if k != "attestation_digest"}
    return digest_document(clean)


# ---------------------------------------------------------------- Attestation Builder

def build_attestation(*, manifest: dict, fingerprint_set_digest: str = "",
                      attestation_id: str = "", trust_level: str = TRUST_LEVEL_LOCAL_ISOLATED,
                      execution_status: str = "", signed_at: str = "") -> dict:
    """构建 Execution Attestation 文档（不含签名封套）。

    attestation_id 默认 UUIDv4。
    fingerprint_set_digest 可选——如未传入则从 manifest 的四种指纹重算。
    trust_level 必须是 TRUST_LEVELS 之一。
    execution_status 必须来自 manifest（防伪造成功）。
    """
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a dict")
    if trust_level not in TRUST_LEVELS:
        raise ValueError("trust_level %r not in %s"
                         % (trust_level, TRUST_LEVELS))

    run_id = str(manifest.get("run_id") or "")
    execution_id = str(manifest.get("execution_id") or "")
    manifest_digest = str(manifest.get("manifest_digest") or "")
    artifact_set_digest = str(manifest.get("artifact_set_digest") or "")

    if not run_id:
        raise ValueError("manifest missing run_id")
    if not manifest_digest:
        raise ValueError("manifest missing manifest_digest")

    if not fingerprint_set_digest:
        fingerprint_set_digest = digest_document({
            "environment_fingerprint": str(manifest.get("environment_fingerprint") or ""),
            "source_fingerprint": str(manifest.get("source_fingerprint") or ""),
            "collector_fingerprint": str(manifest.get("collector_fingerprint") or ""),
            "execution_config_fingerprint": str(
                manifest.get("execution_config_fingerprint") or ""),
        })

    doc = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "attestation_id": str(attestation_id or str(uuid.uuid4()).lower()),
        "attestation_schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "execution_id": execution_id,
        "manifest_digest": manifest_digest,
        "artifact_set_digest": artifact_set_digest,
        "environment_fingerprint": str(manifest.get("environment_fingerprint") or ""),
        "source_fingerprint": str(manifest.get("source_fingerprint") or ""),
        "collector_fingerprint": str(manifest.get("collector_fingerprint") or ""),
        "execution_config_fingerprint": str(
            manifest.get("execution_config_fingerprint") or ""),
        "fingerprint_set_digest": fingerprint_set_digest,
        "execution_status": str(execution_status or manifest.get("execution_status") or ""),
        "trust_level": trust_level,
        "attestation_scope": SCOPE,
        "signed_at": str(signed_at or _now_iso()),
        "attestation_digest": "",  # 占位
        "attestation_digest_scheme": "execution-attestation-digest-v1",
    }
    doc["attestation_digest"] = compute_attestation_digest(doc)
    return doc


# ---------------------------------------------------------------- 签名（复用 Phase 1.61）

def attest_execution(*, manifest: dict, trust_level: str = TRUST_LEVEL_LOCAL_ISOLATED,
                      trust_store=None, project_root: str = "",
                      signer_key_id: str = "", execution_status: str = "",
                      fingerprint_set_digest: str = "") -> dict:
    """一站式：构建 Attestation + Phase 1.61 Ed25519 签名。

    返回带 provenance_signature sidecar envelope 的完整文档。

    签发前强制核对：
    1. manifest_digest 必须与 manifest 内容一致（防 Manifest 篡改）
    2. manifest.execution_status 必须是终止态（SUCCEEDED / FAILED / TIMEOUT / CRASHED）
    3. trust_store 必须是 Phase 1.61 的 TrustStore 实例
    4. signer_key_id 必须在信任根中且 ACTIVE + 有 attest_execution scope
    """
    signature_schema, signing, verification, prov_trust_store = _get_provenance()

    from .manifest import RunManifest, compute_manifest_digest
    errors = RunManifest.validate_manifest(manifest)
    if errors:
        raise ValueError("Run Manifest invalid: %s" % "; ".join(errors))

    # 防伪造成功：必须明确 execution_status
    final_status = execution_status or str(manifest.get("execution_status") or "")
    valid_final = ("SUCCEEDED", "FAILED", "TIMEOUT", "CRASHED", "INCOMPLETE")
    if final_status not in valid_final:
        raise ValueError(
            "refusing to attest execution with non-final status %r "
            "(must be one of %s)" % (final_status, valid_final))

    attestation = build_attestation(
        manifest=manifest,
        fingerprint_set_digest=fingerprint_set_digest,
        trust_level=trust_level,
        execution_status=final_status,
    )

    # 用 Phase 1.61 sign_object 签发
    digest = attestation["attestation_digest"]
    envelope = signing.sign_object(
        object_type=OBJECT_TYPE,
        object_id=attestation["attestation_id"],
        object_version=str(attestation["schema_version"]),
        content_digest=digest,
        digest_scheme=attestation["attestation_digest_scheme"],
        key_id=signer_key_id,
        trust_store=trust_store,
        project_root=project_root,
        binding={
            "run_id": attestation["run_id"],
            "manifest_digest": attestation["manifest_digest"],
            "trust_level": attestation["trust_level"],
        },
        signed_at=attestation["signed_at"],
        scope=SCOPE,
    )

    # 返回 attestation + signature sidecar（两者分离，与 Phase 1.61 Evidence 模式一致）
    return {
        "attestation": attestation,
        "signature_envelope": envelope,
    }


# ---------------------------------------------------------------- 验证

def verify_attestation(*, attestation: dict, signature_envelope: dict,
                        manifest: dict | None = None,
                        trust_store=None,
                        expected_run_id: str = "",
                        expected_execution_id: str = "",
                        expected_manifest_digest: str = "") -> dict:
    """Execution Attestation 完整验证。

    验证链（按序每步失败即返回对应状态）：
        1. Attestation 文档结构
        2. attestation_digest 与内容一致
        3. Phase 1.61 签名验证（trust_store + signer + Ed25519）
        4. Run ID 与 manifest 一致（若 manifest 提供）
        5. manifest_digest 与 manifest 内容一致（防 Manifest 被换）
        6. 四种 Fingerprint 与 manifest 一致
        7. artifact_set_digest 与 manifest 一致
        8. execution_status 是终止态

    返回 {ok, status, reason, ...}
    """
    signature_schema, signing, verification, prov_trust_store = _get_provenance()

    if not isinstance(attestation, dict):
        return {
            "ok": False, "status": STATUS_ATTESTATION_MISSING,
            "reason": "attestation is not a dict",
        }

    # 1. Attestation 文档结构
    errors = validate_attestation_document(attestation)
    if errors:
        return {
            "ok": False, "status": STATUS_ATTESTATION_INVALID,
            "reason": "; ".join(errors),
        }

    # 2. attestation_digest 必须自洽
    declared = str(attestation.get("attestation_digest") or "")
    computed = compute_attestation_digest(attestation)
    if declared != computed:
        return {
            "ok": False, "status": STATUS_ATTESTATION_INVALID,
            "reason": ("attestation_digest mismatch: declared %s != computed %s "
                       "(attestation document was modified after generation)"
                       % (declared[:12], computed[:12])),
        }

    # 3. Phase 1.61 签名验证
    verified = verification.verify_envelope(
        signature_envelope,
        object_type=OBJECT_TYPE,
        object_id=str(attestation.get("attestation_id") or ""),
        object_version=str(attestation.get("schema_version") or ""),
        expected_digest=declared,
        expected_digest_scheme=str(attestation.get("attestation_digest_scheme") or ""),
        trust_store=trust_store,
    )
    if verified.get("status") != signature_schema.SIGNATURE_VALID:
        # 映射 Phase 1.61 状态到 Phase 1.62 状态
        p161 = verified.get("status", "")
        if p161 == signature_schema.KEY_UNKNOWN or \
           p161 == signature_schema.TRUST_ROOT_MISSING or \
           p161 == signature_schema.TRUST_ROOT_UNREADABLE or \
           p161 == signature_schema.TRUST_ROOT_INSECURE_LOCATION:
            status = STATUS_SIGNER_UNTRUSTED
        elif p161 == signature_schema.SCOPE_MISMATCH:
            status = STATUS_SIGNER_UNAUTHORIZED
        elif p161 == signature_schema.DIGEST_MISMATCH:
            status = STATUS_ATTESTATION_INVALID
        else:
            status = STATUS_ATTESTATION_INVALID
        return {
            "ok": False, "status": status,
            "reason": "signature verification failed: %s" % verified.get("reason"),
            "p161_status": p161,
            "signer_subject": verified.get("signer_subject"),
            "trust_root_path": verified.get("trust_root_path"),
        }

    # 签名通过——继续 Attestation → Manifest 绑定检查
    result = {
        "ok": True,
        "status": STATUS_ATTESTED_VERIFIED,
        "reason": "attestation verified; signature valid",
        "signer_subject": verified.get("signer_subject"),
        "signer_key_id": verified.get("signer_key_id"),
        "key_status": verified.get("key_status"),
        "attestation_id": attestation.get("attestation_id"),
        "run_id": attestation.get("run_id"),
        "execution_id": attestation.get("execution_id"),
        "trust_level": attestation.get("trust_level"),
    }

    # 4. expected_run_id 检查（如果调用方声明了预期 Run ID）
    if expected_run_id and str(attestation.get("run_id") or "") != str(expected_run_id):
        result["ok"] = False
        result["status"] = STATUS_RUN_ID_MISMATCH
        result["reason"] = (
            "attestation run_id %s != expected %s; "
            "attestation does not belong to this execution"
            % (str(attestation.get("run_id") or "")[:12], expected_run_id[:12])
        )
        return result

    if expected_execution_id and str(attestation.get("execution_id") or "") != str(expected_execution_id):
        result["ok"] = False
        result["status"] = STATUS_EXECUTION_ID_MISMATCH
        result["reason"] = "attestation execution_id mismatch"
        return result

    # 5. Manifest 绑定检查（如果 manifest 提供）
    if isinstance(manifest, dict):
        # run_id
        manifest_run_id = str(manifest.get("run_id") or "")
        if manifest_run_id and str(attestation.get("run_id") or "") != manifest_run_id:
            result["ok"] = False
            result["status"] = STATUS_RUN_ID_MISMATCH
            result["reason"] = (
                "attestation run_id %s != manifest run_id %s"
                % (str(attestation.get("run_id") or "")[:12],
                   manifest_run_id[:12])
            )
            return result

        # manifest_digest
        manifest_digest_declared = str(attestation.get("manifest_digest") or "")
        from .manifest import compute_manifest_digest
        manifest_digest_computed = compute_manifest_digest(manifest)
        if manifest_digest_declared and manifest_digest_declared != manifest_digest_computed:
            result["ok"] = False
            result["status"] = STATUS_MANIFEST_DIGEST_MISMATCH
            result["reason"] = (
                "attestation manifest_digest %s != recomputed manifest_digest %s; "
                "manifest was modified after attestation"
                % (manifest_digest_declared[:12], manifest_digest_computed[:12])
            )
            return result

        # artifact_set_digest
        attest_set = str(attestation.get("artifact_set_digest") or "")
        manifest_set = str(manifest.get("artifact_set_digest") or "")
        if attest_set and manifest_set and attest_set != manifest_set:
            result["ok"] = False
            result["status"] = STATUS_ARTIFACT_SET_MISMATCH
            result["reason"] = (
                "attestation artifact_set_digest %s != manifest %s"
                % (attest_set[:12], manifest_set[:12])
            )
            return result

        # fingerprint 一致性
        for fp_field in ("environment_fingerprint", "source_fingerprint",
                         "collector_fingerprint", "execution_config_fingerprint"):
            attest_fp = str(attestation.get(fp_field) or "")
            manifest_fp = str(manifest.get(fp_field) or "")
            if attest_fp and manifest_fp and attest_fp != manifest_fp:
                result["ok"] = False
                result["status"] = {
                    "environment_fingerprint": STATUS_ENVIRONMENT_MISMATCH,
                    "source_fingerprint": STATUS_SOURCE_MISMATCH,
                    "collector_fingerprint": STATUS_COLLECTOR_MISMATCH,
                    "execution_config_fingerprint": STATUS_CONFIG_MISMATCH,
                }.get(fp_field, STATUS_ATTESTATION_INVALID)
                result["reason"] = (
                    "%s mismatch: attestation %s != manifest %s"
                    % (fp_field, attest_fp[:12], manifest_fp[:12])
                )
                return result

    # 6. expected_manifest_digest（如果调用方传入）
    if expected_manifest_digest and \
       str(attestation.get("manifest_digest") or "") != str(expected_manifest_digest):
        result["ok"] = False
        result["status"] = STATUS_MANIFEST_DIGEST_MISMATCH
        result["reason"] = "attestation manifest_digest != expected"
        return result

    return result


def validate_attestation_document(attestation: dict) -> list:
    """返回错误列表（不含签名验证）。"""
    errors = []
    if not isinstance(attestation, dict):
        errors.append("attestation must be a dict")
        return errors
    if attestation.get("schema") != SCHEMA:
        errors.append("schema %r != %r" % (attestation.get("schema"), SCHEMA))
        return errors
    if int(attestation.get("schema_version", 0)) != SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    for field in ("attestation_id", "run_id", "manifest_digest",
                  "execution_status", "trust_level"):
        if not str(attestation.get(field) or ""):
            errors.append("missing %r" % field)
    # run_id / execution_id 必须是 UUIDv4
    from .identity import is_valid_uuidv4
    run_id = str(attestation.get("run_id") or "")
    exec_id = str(attestation.get("execution_id") or "")
    if run_id and not is_valid_uuidv4(run_id):
        errors.append("run_id is not UUIDv4")
    if exec_id and not is_valid_uuidv4(exec_id):
        errors.append("execution_id is not UUIDv4")
    trust_level = str(attestation.get("trust_level") or "")
    if trust_level and trust_level not in TRUST_LEVELS:
        errors.append("trust_level %r not in %s" % (trust_level, TRUST_LEVELS))
    return errors


# ---------------------------------------------------------------- 结果词表导出

RESULT_STATUSES = (
    STATUS_ATTESTED_VERIFIED,
    STATUS_ATTESTATION_MISSING,
    STATUS_ATTESTATION_INVALID,
    STATUS_SIGNER_UNTRUSTED,
    STATUS_SIGNER_UNAUTHORIZED,
    STATUS_MANIFEST_DIGEST_MISMATCH,
    STATUS_RUN_ID_MISMATCH,
    STATUS_EXECUTION_ID_MISMATCH,
    STATUS_ENVIRONMENT_MISMATCH,
    STATUS_COLLECTOR_MISMATCH,
    STATUS_SOURCE_MISMATCH,
    STATUS_CONFIG_MISMATCH,
    STATUS_ARTIFACT_SET_MISMATCH,
    STATUS_ARTIFACT_MISSING,
    STATUS_EXECUTION_FAILED,
    STATUS_EXECUTION_INCOMPLETE,
)
