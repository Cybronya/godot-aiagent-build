#!/usr/bin/env python3
"""密钥身份与授权模型（Phase 1.61）。

密钥的身份**只**来自外部信任根（trust_store），绝不来自项目工作区内的
自报登记。本模块提供：

  - scope/对象类型授权核对（签名者授权范围）；
  - 私钥种子的存取（工作区外、0600 权限、永不入日志）。

私钥存放：`<trust_dir>/keys/<key_id>.seed`（32 字节 Ed25519 seed 的 hex）。

私钥安全边界（任务书 §8.1）：

  - 私钥**永不**提交 Git、永不写入测试报告 / 日志 / 普通配置文件；
  - 私钥文件拒绝写入或读取项目工作区内的路径（与信任根同一边界规则）；
  - 本模块的任何异常消息都不得携带种子内容（错误只报路径与 IO 类别）。

授权模型：信任根中每条密钥声明 scopes；签名封套声明 scope；
验证时必须满足 `envelope.scope == SCOPE_FOR_TYPE[object_type]`
且 `envelope.scope ∈ key.scopes`，否则 SCOPE_MISMATCH（fail-closed）。
"""

from __future__ import annotations

import os
import stat

from . import signature_schema as schema
from .trust_store import (KEYS_SUBDIRNAME, STATUS_ACTIVE, TrustStoreError,
                          is_inside_path)

SEED_HEX_LENGTH = 64  # Ed25519 seed = 32 bytes


def check_authorized(key_record: dict, scope: str) -> tuple[bool, str]:
    """核对签名者是否具有对应 scope 的签发权限。

    返回 (authorized, reason)。密钥必须为 ACTIVE 才能签发**新**对象；
    RETIRED 密钥的历史签名仍可验证（由 verification 控制该区分）。
    """
    if not isinstance(key_record, dict):
        return False, "no key record"
    scopes = key_record.get("scopes") or []
    if scope not in scopes:
        return False, ("key %s is not authorized for scope %r (authorized: %s)"
                       % (key_record.get("key_id"), scope,
                          ", ".join(sorted(str(item) for item in scopes)) or "none"))
    return True, ""


def can_sign_new_objects(key_record: dict) -> tuple[bool, str]:
    """只有 ACTIVE 密钥可以签发新对象（RETIRED/REVOKED 拒绝签发）。"""
    status = str((key_record or {}).get("status"))
    if status == STATUS_ACTIVE:
        return True, ""
    return False, ("key %s is %s; only ACTIVE keys may sign new objects"
                   % ((key_record or {}).get("key_id"), status or "unknown"))


def seed_path(trust_dir: str, key_id: str) -> str:
    """私钥种子文件路径（trust_dir 必须位于工作区外）。"""
    return os.path.join(str(trust_dir), KEYS_SUBDIRNAME,
                        "%s.seed" % str(key_id))


def _refuse_workspace(path: str, project_root: str, what: str) -> None:
    if is_inside_path(path, project_root):
        raise TrustStoreError(
            "refusing to %s %s inside the project workspace (%r); private key "
            "material must live outside the workspace" % (what, what, path))


def write_seed(trust_dir: str, key_id: str, seed_hex: str, *,
               project_root: str) -> str:
    """把私钥种子写入工作区外的密钥文件（0600，Windows 下尽力收紧）。

    秘密内容不出现在任何异常消息里。
    """
    if not isinstance(seed_hex, str) or len(seed_hex) != SEED_HEX_LENGTH:
        raise TrustStoreError("seed must be a %d-char hex string"
                              % SEED_HEX_LENGTH)
    target = seed_path(trust_dir, key_id)
    _refuse_workspace(target, project_root, "store a private key")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(seed_hex + "\n")
    os.replace(tmp, target)
    try:  # 权限收紧：POSIX 下 0600；Windows 无 POSIX 位，尽力而为
        os.chmod(target, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return target


def load_seed(trust_dir: str, key_id: str, *, project_root: str) -> str:
    """读取私钥种子；工作区内路径一律拒绝；错误消息不含秘密内容。"""
    target = seed_path(trust_dir, key_id)
    _refuse_workspace(target, project_root, "load a private key from")
    if not os.path.isfile(target):
        raise TrustStoreError("no signing seed for %r at %r" % (key_id, target))
    try:
        with open(target, "r", encoding="utf-8") as handle:
            seed_hex = (handle.read() or "").strip()
    except OSError as exc:
        raise TrustStoreError("signing seed unreadable (io error): %s"
                              % exc.__class__.__name__) from exc
    if len(seed_hex) != SEED_HEX_LENGTH:
        raise TrustStoreError("signing seed for %r is malformed (wrong length)"
                              % key_id)
    return seed_hex
