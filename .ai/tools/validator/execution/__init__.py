#!/usr/bin/env python3
"""Execution Provenance —— 可验证的执行来源体系（Phase 1.62）。

模块构成：
    identity.py    Execution Identity（Run ID / Execution ID，UUIDv4 + 生命周期）
    fingerprint.py 四种独立指纹（Environment / Source / Collector / Config）
    manifest.py    Run Manifest Schema + 规范化序列化
    binding.py     Artifact-to-Run Binding（Phase 1.57 扩展）
    attestation.py Execution Attestation 签发 + 验证（Phase 1.61 Ed25519 复用）

信任边界（诚实声明）：
    本模块能证明「谁在什么环境下，对什么代码版本，用什么采集器，
    在什么参数下，产生了哪些 Artifact，并由谁签发了执行证明」。

    它**不能**（本阶段实现范围）：
    - 证明 Godot 没被篡改（执行器与 Godot 同权限边界）
    - 证明采集器没被替换（本地隔离原型）
    - 证明执行器私钥没被攻击者读取（同一用户权限）
    - 提供硬件级可信执行证明

    本阶段实现的是 LOCAL_ISOLATED 等级。
    EXTERNAL_TRUSTED_RUNNER / HARDWARE_ATTESTED —— DEFERRED。
"""

from .identity import (ExecutionIdentity, new_run_id, new_execution_id,  # noqa: F401
                       is_valid_uuidv4, validate_run_id)
from .fingerprint import (ExecutionFingerprints, collect_all,  # noqa: F401
                          collect_environment, collect_source,
                          collect_collector, collect_execution_config,
                          canonical_json, digest_document,
                          classify_environment_change)
from .manifest import (RunManifest, make_artifact_entry,  # noqa: F401
                        compute_artifact_set_digest,
                        compute_manifest_digest, canonicalize_manifest)
from .binding import BoundArtifactResolver, BindingError  # noqa: F401
from .attestation import (build_attestation, attest_execution,  # noqa: F401
                          verify_attestation, validate_attestation_document,
                          compute_attestation_digest,
                          OBJECT_TYPE as ATTESTATION_OBJECT_TYPE,
                          SCOPE as ATTESTATION_SCOPE,
                          SCHEMA as ATTESTATION_SCHEMA,
                          SCHEMA_VERSION as ATTESTATION_SCHEMA_VERSION,
                          TRUST_LEVELS as ATTESTATION_TRUST_LEVELS,
                          RESULT_STATUSES as ATTESTATION_RESULT_STATUSES,
                          STATUS_ATTESTED_VERIFIED,
                          STATUS_ATTESTATION_MISSING,
                          STATUS_ATTESTATION_INVALID)

__all__ = [name for name in dir() if not name.startswith("_")]
