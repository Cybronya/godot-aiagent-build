#!/usr/bin/env python3
"""Provenance：独立信任根与来源签名验证（Phase 1.61）。

模块构成：

    signature_schema  封套 Schema / 规范化序列化 / 结果词表
    trust_store       外部信任根加载（工作区外）+ 密钥生命周期 ACTIVE/RETIRED/REVOKED
    key_metadata      密钥身份与 scope 授权 + 私钥种子存取（永不入工作区）
    signing           Ed25519 签名（PyNaCl/libsodium；不自研密码学原语）
    verification      fail-closed 验证管线 + 签名策略（allow_legacy / require）
    provenance_cli    keygen / rotate / revoke / status / sign / verify

信任边界：签名证明"谁签署了什么摘要"，不证明执行过程真实。
"""

from . import signature_schema  # noqa: F401
from .signature_schema import (ALGORITHM, OBJECT_BASELINE, OBJECT_EVIDENCE,  # noqa: F401
                               OBJECT_HOLDOUT, SCOPE_APPROVE_BASELINE,
                               SCOPE_FOR_TYPE, SCOPE_ISSUE_EVIDENCE,
                               SCOPE_SEAL_HOLDOUT, SIGNATURE_MISSING,
                               SIGNATURE_VALID, TRUST_CRYPTO_VERIFIED,
                               TRUST_LEGACY_APPROVED, TRUST_SIGNATURE_INVALID,
                               TRUST_SIGNATURE_REQUIRED)

from .trust_store import (TrustStore, TrustStoreError,  # noqa: F401
                          STATUS_ACTIVE, STATUS_RETIRED, STATUS_REVOKED,
                          TRUST_DIRNAME, ENV_TRUST_ROOT,
                          ENV_REVOCATIONS, default_trust_root_path,
                          derive_key_id, is_inside_path)

from .signing import (build_envelope, generate_and_register, sign_envelope,  # noqa: F401
                      sign_object)

from .verification import (evaluate_signature, verify_envelope,  # noqa: F401
                           POLICY_ALLOW_LEGACY, POLICY_REQUIRE_SIGNATURE)

__all__ = [name for name in dir() if not name.startswith("_")]
