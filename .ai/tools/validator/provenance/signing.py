#!/usr/bin/env python3
"""Provenance 签名（Ed25519，PyNaCl/libsodium）（Phase 1.61）。

**不自行实现任何密码学原语**：Ed25519 全部由 PyNaCl（libsodium 绑定）提供。
nacl 延迟导入：库缺失时签名能力标记不可用（LIBRARY_UNAVAILABLE），
require 场景必须 fail-closed，不得静默降级为"无签名放行"。

签名流程：

    1. 从外部信任根目录加载私钥种子（工作区外，见 key_metadata）；
    2. 构建封套（对象类型/ID/版本/摘要/scope/binding）；
    3. 对封套（去 signature 字段）的规范化 JSON 字节做 Ed25519 签名；
    4. base64 编码写入封套 signature 字段。

签发前强制核对（fail-closed）：

    - 密钥必须存在于外部信任根且状态为 ACTIVE（RETIRED/REVOKED 不可签发新对象）；
    - 封套 scope 必须在密钥授权 scopes 内；
    - 签名者身份 = 信任根中该 key_id 的记录（subject 等取自信任根，
      不接受工作区自报身份）。
"""

from __future__ import annotations

import base64
import binascii
import os
from datetime import datetime, timezone

from . import signature_schema as schema
from .key_metadata import (can_sign_new_objects, check_authorized, load_seed,
                           write_seed)
from .trust_store import (KEY_STATUSES, STATUS_ACTIVE, TrustStore,
                          TrustStoreError, derive_key_id, is_inside_path,
                          now_iso)


def load_nacl():
    """延迟加载 PyNaCl；返回 (module|None, error_text)。"""
    try:
        import nacl.signing  # noqa: PLC0415 - 延迟导入：库缺失时给 fail-closed 语义
        return nacl.signing, ""
    except ImportError as exc:
        return None, ("PyNaCl is not available (%s); cryptographic signing is "
                      "unavailable and require-signature mode must fail closed"
                      % exc.__class__.__name__)


def generate_seed_hex() -> str:
    """生成 32 字节随机 Ed25519 种子（hex）；库不可用时报错。"""
    module, error = load_nacl()
    if module is None:
        raise TrustStoreError(error)
    return binascii.hexlify(bytes(module.SigningKey.generate())).decode("ascii")


def seed_to_public_b64(seed_hex: str) -> str:
    """由种子推导公钥（raw 32 字节的 base64）。"""
    module, error = load_nacl()
    if module is None:
        raise TrustStoreError(error)
    signing_key = module.SigningKey(bytes.fromhex(seed_hex))
    return base64.b64encode(bytes(signing_key.verify_key)).decode("ascii")


def generate_and_register(*, subject: str, scopes: list, trust_store: TrustStore,
                          project_root: str) -> dict:
    """生成密钥对：私钥种子写入信任目录（工作区外），公钥登记入信任根。

    这是 keygen 的核心动作。信任根不存在时先初始化（仍只写工作区外路径）。
    返回登记记录（含 key_id）。
    """
    if is_inside_path(trust_store.trust_dir(), project_root):
        raise TrustStoreError(
            "refusing to generate keys inside the project workspace (%r)"
            % trust_store.trust_dir())
    if not os.path.isfile(trust_store.trust_root_path()):
        trust_store.initialize()
    seed_hex = generate_seed_hex()
    public_b64 = seed_to_public_b64(seed_hex)
    key_id = derive_key_id(public_b64)
    write_seed(trust_store.trust_dir(), key_id, seed_hex,
               project_root=project_root)
    record = trust_store.add_key(public_b64, subject=subject,
                                 scopes=list(scopes or []), key_id=key_id)
    return record


def build_envelope(*, object_type: str, object_id, object_version,
                   content_digest: str, digest_scheme: str,
                   signer_key_id: str, binding: dict | None = None,
                   signed_at: str = "", scope: str = "") -> dict:
    """构建签名封套（不含 signature 字段）。

    scope 缺省取 SCOPE_FOR_TYPE[object_type]；显式传入其他 scope 会在
    验证侧被拒（跨用途复用不允许）。
    """
    if object_type not in schema.OBJECT_TYPES:
        raise TrustStoreError("unknown object_type %r" % object_type)
    envelope = {
        "schema": schema.SCHEMA,
        "schema_version": schema.SCHEMA_VERSION,
        "object_type": str(object_type),
        "object_id": str(object_id),
        "object_version": str(object_version),
        "content_digest": str(content_digest),
        "digest_scheme": str(digest_scheme),
        "scope": str(scope or schema.SCOPE_FOR_TYPE[object_type]),
        "signer_key_id": str(signer_key_id),
        "signature_algorithm": schema.ALGORITHM,
        "signed_at": str(signed_at or now_iso()),
        "binding": dict(binding or {}),
    }
    return envelope


def sign_envelope(envelope: dict, *, trust_store: TrustStore,
                  project_root: str) -> dict:
    """用封套声明的 signer_key_id 对应私钥签名（fail-closed）。

    签发前核对：密钥存在（信任根）+ ACTIVE + scope 授权。
    """
    module, error = load_nacl()
    if module is None:
        raise TrustStoreError(error)
    errors = schema.structure_errors(envelope, require_signature=False)
    if errors:
        raise TrustStoreError("envelope malformed: %s" % "; ".join(errors))
    expected_scope = schema.SCOPE_FOR_TYPE.get(str(envelope.get("object_type")))
    if str(envelope.get("scope")) != str(expected_scope):
        raise TrustStoreError(
            "envelope scope %r does not match object_type %r (required %r); "
            "refusing to sign a mismatched envelope"
            % (envelope.get("scope"), envelope.get("object_type"), expected_scope))
    key_id = str(envelope.get("signer_key_id"))
    record, _loaded = trust_store.key_record(key_id)
    if record is None:
        raise TrustStoreError("signer %r is not in the external trust root; "
                              "refusing to sign" % key_id)
    ok, reason = can_sign_new_objects(record)
    if not ok:
        raise TrustStoreError(reason)
    ok, reason = check_authorized(record, str(envelope.get("scope")))
    if not ok:
        raise TrustStoreError(reason)
    seed_hex = load_seed(trust_store.trust_dir(), key_id,
                         project_root=project_root)
    signing_key = module.SigningKey(bytes.fromhex(seed_hex))
    message = schema.signed_message(envelope)
    signature = signing_key.sign(message).signature
    envelope = dict(envelope)
    envelope["signature"] = base64.b64encode(signature).decode("ascii")
    return envelope


def sign_object(*, object_type: str, object_id, object_version,
                content_digest: str, digest_scheme: str, key_id: str,
                trust_store: TrustStore, project_root: str,
                binding: dict | None = None, signed_at: str = "",
                scope: str = "") -> dict:
    """一站式：构建封套并签名（key_id 必须在信任根中且 ACTIVE + 授权）。"""
    envelope = build_envelope(object_type=object_type, object_id=object_id,
                              object_version=object_version,
                              content_digest=content_digest,
                              digest_scheme=digest_scheme,
                              signer_key_id=key_id, binding=binding,
                              signed_at=signed_at, scope=scope)
    return sign_envelope(envelope, trust_store=trust_store,
                         project_root=project_root)


def missing_library_error() -> str:
    return load_nacl()[1]
