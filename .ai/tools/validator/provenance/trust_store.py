#!/usr/bin/env python3
"""外部信任根加载与密钥生命周期（Phase 1.61）。

独立信任根（任务书 §2.1）：

    公钥必须来自**项目工作区写权限之外**的可信来源。本模块实现的来源：

      1. 默认位置：`<user home>/.provenance_trust/trust_root.json`
         （用户管理的独立公钥文件；位于工作区之外）。
      2. 环境变量 `PROVENANCE_TRUST_ROOT`：显式指定信任根文件路径
         （CI Secret / 受保护变量的落地形式）。
      3. 构造参数 `trust_root_path=`：调用方显式注入（测试用）。

    **硬规则**：无论来源如何，解析后的信任根路径若位于项目工作区内，
    一律拒绝加载（TRUST_ROOT_INSECURE_LOCATION，fail-closed）——
    把公钥放进工作区不能称为独立信任根（任务书 §2.1 / 攻击场景 A16）。

密钥生命周期（任务书 §7，最小可用）：

    ACTIVE   可签发新对象；历史签名可验证
    RETIRED  不可签发新对象；历史签名**可继续验证**（轮换不改变历史签名）
    REVOKED  撤销。默认撤销策略 reject：其签名验证一律拒绝。

    转换：ACTIVE -> RETIRED / REVOKED；RETIRED -> REVOKED；REVOKED 为终态。

撤销来源边界（如实声明）：

    信任根文件与撤销覆盖文件（`PROVENANCE_REVOCATIONS`）都是**用户管理的
    工作区外文件**。本环境没有自动化撤销基础设施（无 CI / KMS），因此
    "密钥未被撤销"的证明力取决于用户对该目录的保护，不取决于项目数据。
    项目工作区内任何自报撤销记录一律无效（同边界可改写）。

key_id 唯一性：信任根加载时强校验；重复 key_id 视为信任根损坏（fail-closed）。
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

from . import signature_schema as schema

TRUST_DIRNAME = ".provenance_trust"
TRUST_ROOT_FILENAME = "trust_root.json"
KEYS_SUBDIRNAME = "keys"

ENV_TRUST_ROOT = "PROVENANCE_TRUST_ROOT"
ENV_REVOCATIONS = "PROVENANCE_REVOCATIONS"

STATUS_ACTIVE = "ACTIVE"
STATUS_RETIRED = "RETIRED"
STATUS_REVOKED = "REVOKED"
KEY_STATUSES = (STATUS_ACTIVE, STATUS_RETIRED, STATUS_REVOKED)

LEGAL_KEY_TRANSITIONS = {
    STATUS_ACTIVE: {STATUS_RETIRED, STATUS_REVOKED},
    STATUS_RETIRED: {STATUS_REVOKED},
    STATUS_REVOKED: set(),
}

# 撤销策略：REVOKED 密钥的签名如何处理（任务书 §7.3：必须按明确策略处理）
REVOCATION_POLICY_REJECT = "reject"       # 默认：撤销密钥的签名一律拒绝
REVOCATION_POLICIES = (REVOCATION_POLICY_REJECT,)

SOURCE_DEFAULT_USER = "user_home_default"
SOURCE_ENV = "env_override"
SOURCE_EXPLICIT = "explicit"

TRUST_ROOT_OK = "TRUST_ROOT_OK"
TRUST_ROOT_OK_EMPTY = "TRUST_ROOT_OK_EMPTY"


class TrustStoreError(ValueError):
    """信任根操作非法（损坏 / 路径不安全 / 转换非法 / 字段缺失）。"""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolved(path: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(str(path))))


def is_inside_path(candidate: str, parent: str) -> bool:
    """candidate 是否位于 parent 目录之内（Windows 大小写不敏感）。"""
    try:
        child = _resolved(candidate)
        root = _resolved(parent)
    except (OSError, ValueError):
        return False
    if child == root:
        return False
    try:
        return os.path.commonpath([child, root]) == root
    except ValueError:
        return False


def derive_key_id(public_key_b64: str) -> str:
    """从公钥确定性派生唯一 key_id（PROVKEY-<sha256(public)[:16]>）。"""
    raw = hashlib.sha256(str(public_key_b64).encode("utf-8")).hexdigest()
    return "PROVKEY-%s" % raw[:16]


def default_trust_root_path(project_root: str = "") -> str:
    """本项目专属的外部信任根路径（用户级、工作区外）。

    `<home>/.provenance_trust/<project-slug>/trust_root.json`，其中 slug =
    项目目录名 + 绝对路径摘要前 12 位 —— 同机多项目的信任根互不混用
    （一个项目的密钥不能签另一个项目的对象）。
    """
    root = os.path.realpath(os.path.abspath(project_root or default_project_root()))
    slug_raw = hashlib.sha256(root.replace("\\", "/").lower().encode("utf-8")).hexdigest()
    slug = "%s-%s" % (os.path.basename(root), slug_raw[:12])
    return os.path.join(os.path.expanduser("~"), ".provenance_trust", slug,
                        TRUST_ROOT_FILENAME)


def default_project_root() -> str:
    """本项目根目录（trust_store.py 位于 <root>/.ai/tools/validator/provenance/）。"""
    here = os.path.abspath(__file__)
    for _ in range(5):  # trust_store.py -> provenance -> validator -> tools -> .ai -> <root>
        here = os.path.dirname(here)
    return here


class TrustStore:
    """外部信任根：只从工作区之外加载可信公钥与密钥生命周期状态。"""

    def __init__(self, trust_root_path: str = "", *,
                 project_root: str = "", revocations_path: str = ""):
        self.project_root = os.path.realpath(
            project_root or default_project_root())
        self._explicit_path = str(trust_root_path or "")
        self._revocations_path = str(revocations_path or "")
        self._loaded = False
        self._load_result: dict = {}
        self._document: dict | None = None

    # ------------------------------------------------------------ 路径解析
    def trust_root_path(self) -> str:
        if self._explicit_path:
            return self._explicit_path
        env = os.environ.get(ENV_TRUST_ROOT, "")
        if env:
            return env
        return default_trust_root_path(self.project_root)

    def trust_dir(self) -> str:
        return os.path.dirname(os.path.abspath(self.trust_root_path()))

    def keys_dir(self) -> str:
        return os.path.join(self.trust_dir(), KEYS_SUBDIRNAME)

    def source_kind(self) -> str:
        if self._explicit_path:
            return SOURCE_EXPLICIT
        if os.environ.get(ENV_TRUST_ROOT, ""):
            return SOURCE_ENV
        return SOURCE_DEFAULT_USER

    def _resolve_load(self) -> dict:
        """解析待加载路径并执行工作区边界检查（fail-closed）。"""
        path = self.trust_root_path()
        if not path:
            return {"ok": False, "status": schema.TRUST_ROOT_MISSING,
                    "reason": "no trust root path configured", "path": "",
                    "source_kind": self.source_kind()}
        if is_inside_path(path, self.project_root):
            return {"ok": False, "status": schema.TRUST_ROOT_INSECURE_LOCATION,
                    "reason": ("trust root path %r resolves inside the project "
                               "workspace; workspace files cannot be a trust root"
                               % path),
                    "path": path, "source_kind": self.source_kind()}
        if not os.path.isfile(path):
            return {"ok": False, "status": schema.TRUST_ROOT_MISSING,
                    "reason": ("no trust root at %r; provision one outside the "
                               "workspace (provenance_cli.py keygen)" % path),
                    "path": path, "source_kind": self.source_kind()}
        return {"ok": True, "status": "", "reason": "", "path": path,
                "source_kind": self.source_kind()}

    # ------------------------------------------------------------ 加载
    def load(self, *, force: bool = False) -> dict:
        """加载并校验信任根。结果缓存；force=True 重新读取。

        返回 {ok, status, reason, detail, path, source_kind, keys, document}。
        ok=False 时 status ∈ TRUST_ROOT_MISSING / TRUST_ROOT_UNREADABLE /
        TRUST_ROOT_INSECURE_LOCATION（一律 fail-closed，调用方不得降级）。
        """
        if self._loaded and not force:
            return self._load_result
        resolved = self._resolve_load()
        if not resolved["ok"]:
            self._load_result = dict(resolved, ok=False, detail="",
                                     keys=[], document=None)
            self._loaded = True
            return self._load_result
        path = resolved["path"]
        try:
            with open(path, "r", encoding="utf-8") as handle:
                document = json.load(handle)
        except (OSError, ValueError) as exc:
            self._load_result = {"ok": False, "status": schema.TRUST_ROOT_UNREADABLE,
                                 "reason": "trust root unreadable", "detail": str(exc),
                                 "path": path, "source_kind": resolved["source_kind"],
                                 "keys": [], "document": None}
            self._loaded = True
            return self._load_result
        errors = self._validate_document(document)
        if errors:
            self._load_result = {"ok": False, "status": schema.TRUST_ROOT_UNREADABLE,
                                 "reason": "trust root malformed", "detail": "; ".join(errors),
                                 "path": path, "source_kind": resolved["source_kind"],
                                 "keys": [], "document": None}
            self._loaded = True
            return self._load_result
        keys = [dict(record) for record in document.get("keys") or []]
        self._apply_revocations(keys)
        self._document = document
        self._load_result = {"ok": True, "status": TRUST_ROOT_OK,
                             "reason": "external trust root loaded",
                             "detail": "", "path": path,
                             "source_kind": resolved["source_kind"],
                             "keys": keys, "document": document}
        self._loaded = True
        return self._load_result

    @staticmethod
    def _validate_document(document) -> list:
        if not isinstance(document, dict):
            return ["trust root must be a JSON object"]
        errors = []
        if document.get("schema") != schema.TRUST_ROOT_SCHEMA:
            errors.append("unsupported trust root schema %r"
                          % document.get("schema"))
        if document.get("schema_version") != schema.TRUST_ROOT_SCHEMA_VERSION:
            errors.append("unsupported trust root schema_version %r"
                          % document.get("schema_version"))
        keys = document.get("keys")
        if not isinstance(keys, list):
            errors.append("trust root must carry a keys list")
            return errors
        # 空列表合法（keygen 初始化后、登记第一把密钥前）；此时任何验签都会
        # 得到 KEY_UNKNOWN，fail-closed 语义不受影响。
        seen = set()
        for index, record in enumerate(keys):
            if not isinstance(record, dict):
                errors.append("keys[%d] must be an object" % index)
                continue
            for field in ("key_id", "public_key", "algorithm", "subject",
                          "scopes", "status", "created_at"):
                if field not in record:
                    errors.append("keys[%d] missing %r" % (index, field))
            if record.get("algorithm") != schema.ALGORITHM:
                errors.append("keys[%d] unsupported algorithm %r"
                              % (index, record.get("algorithm")))
            if record.get("status") not in KEY_STATUSES:
                errors.append("keys[%d] unknown key status %r"
                              % (index, record.get("status")))
            key_id = str(record.get("key_id") or "")
            if key_id in seen:
                errors.append("duplicate key_id %r (key ids must be unique)" % key_id)
            seen.add(key_id)
            scopes = record.get("scopes")
            if not isinstance(scopes, list) or \
                    any(item not in schema.SCOPES for item in scopes):
                errors.append("keys[%d] scopes invalid" % index)
        return errors

    def _apply_revocations(self, keys: list) -> None:
        """应用外部撤销覆盖（只允许降级到 REVOKED；工作区内文件已在上游拒收）。"""
        path = self._revocations_path or os.environ.get(ENV_REVOCATIONS, "")
        if not path or not os.path.isfile(path):
            return
        if is_inside_path(path, self.project_root):
            raise TrustStoreError(
                "revocations file %r is inside the project workspace; "
                "workspace data cannot revoke external keys" % path)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                document = json.load(handle)
        except (OSError, ValueError) as exc:
            raise TrustStoreError("revocations file unreadable: %s" % exc) from exc
        if document.get("schema") != schema.REVOCATIONS_SCHEMA:
            raise TrustStoreError("unsupported revocations schema %r"
                                  % document.get("schema"))
        for item in document.get("revocations") or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("status")) != STATUS_REVOKED:
                continue  # 覆盖文件只能撤销，不能复活密钥
            for record in keys:
                if str(record.get("key_id")) == str(item.get("key_id")):
                    record["status"] = STATUS_REVOKED
                    record.setdefault("status_history", []).append({
                        "status": STATUS_REVOKED,
                        "at": str(item.get("at") or now_iso()),
                        "source": str(item.get("source") or "revocations_file")})

    # ------------------------------------------------------------ 查询
    def key_record(self, key_id: str) -> tuple[dict | None, dict]:
        """返回 (密钥记录, load 结果)。信任根不可用时记录为 None（fail-closed）。"""
        loaded = self.load()
        if not loaded["ok"]:
            return None, loaded
        for record in loaded["keys"]:
            if str(record.get("key_id")) == str(key_id):
                return record, loaded
        return None, loaded

    def trust_summary(self) -> dict:
        """信任根概况（只含公开信息，供报告使用）。"""
        loaded = self.load()
        return {
            "ok": loaded["ok"],
            "status": loaded["status"] or TRUST_ROOT_OK,
            "reason": loaded["reason"],
            "path": loaded.get("path", ""),
            "source_kind": loaded.get("source_kind", ""),
            "keys": [{"key_id": record.get("key_id"),
                      "status": record.get("status"),
                      "subject": record.get("subject"),
                      "scopes": list(record.get("scopes") or []),
                      "created_at": record.get("created_at")}
                     for record in loaded.get("keys") or []],
        }

    # ------------------------------------------------------------ 生命周期写操作
    def _write_document(self, document: dict, path: str | None = None) -> None:
        target = path or self.trust_root_path()
        if is_inside_path(target, self.project_root):
            raise TrustStoreError(
                "refusing to write a trust root inside the project workspace: %r"
                % target)
        os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
        tmp = target + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp, target)
        self._loaded = False  # 下次 load(force 效果) 重新读取
        self._document = None

    def initialize(self, *, force: bool = False) -> dict:
        """在工作区外初始化一个空的信任根文件（已存在且非 force 则拒绝）。"""
        document = {"schema": schema.TRUST_ROOT_SCHEMA,
                    "schema_version": schema.TRUST_ROOT_SCHEMA_VERSION,
                    "created_at": now_iso(),
                    "note": "user-managed external trust root (outside the "
                            "project workspace); keep this file under user control",
                    "keys": []}
        target = self.trust_root_path()
        if os.path.isfile(target) and not force:
            raise TrustStoreError("trust root already exists at %r" % target)
        self._write_document(document)
        return document

    def _current_document(self) -> dict:
        loaded = self.load()
        if not loaded["ok"]:
            raise TrustStoreError("trust root unavailable: %s (%s)"
                                  % (loaded["status"], loaded["reason"]))
        return dict(loaded["document"])

    def add_key(self, public_key_b64: str, *, subject: str, scopes: list,
                status: str = STATUS_ACTIVE, algorithm: str = schema.ALGORITHM,
                key_id: str = "") -> dict:
        """向信任根添加一条密钥（key_id 唯一性强校验）。"""
        if algorithm != schema.ALGORITHM:
            raise TrustStoreError("unsupported algorithm %r" % algorithm)
        if status not in KEY_STATUSES:
            raise TrustStoreError("unknown key status %r" % status)
        if any(item not in schema.SCOPES for item in (scopes or [])):
            raise TrustStoreError("scopes must be a subset of %s"
                                  % (", ".join(schema.SCOPES)))
        if not str(subject or "").strip():
            raise TrustStoreError("key requires a subject")
        document = self._current_document()
        key_id = str(key_id or derive_key_id(public_key_b64))
        for record in document.get("keys") or []:
            if str(record.get("key_id")) == key_id:
                raise TrustStoreError("key_id %r already exists (must be unique)"
                                      % key_id)
        record = {
            "key_id": key_id,
            "public_key": str(public_key_b64),
            "algorithm": algorithm,
            "subject": str(subject),
            "scopes": [str(item) for item in scopes or []],
            "status": status,
            "created_at": now_iso(),
            "status_history": [{"status": status, "at": now_iso(),
                                "source": "trust_store.add_key"}],
        }
        document["keys"].append(record)
        self._write_document(document)
        return dict(record)

    def set_key_status(self, key_id: str, new_status: str, *,
                       reason: str = "", source: str = "user") -> dict:
        """显式状态转换（非法转换拒绝；历史签名的原始内容不受影响）。"""
        if new_status not in KEY_STATUSES:
            raise TrustStoreError("unknown key status %r" % new_status)
        document = self._current_document()
        record = None
        for item in document.get("keys") or []:
            if str(item.get("key_id")) == str(key_id):
                record = item
                break
        if record is None:
            raise TrustStoreError("unknown key %r" % key_id)
        current = str(record.get("status"))
        if new_status == current:
            raise TrustStoreError("key %r is already %s" % (key_id, current))
        if new_status not in LEGAL_KEY_TRANSITIONS.get(current, set()):
            raise TrustStoreError("illegal key lifecycle transition %s -> %s"
                                  % (current, new_status))
        record["status"] = new_status
        record.setdefault("status_history", []).append(
            {"status": new_status, "at": now_iso(), "source": str(source),
             "reason": str(reason or "")})
        self._write_document(document)
        return dict(record)

    def rotate(self, new_public_key_b64: str, *, new_subject: str,
               new_scopes: list, retiring_key_id: str,
               reason: str = "") -> dict:
        """轮换：新密钥 ACTIVE + 旧密钥 RETIRED（原子两步，同一文档写入）。"""
        document = self._current_document()
        old = None
        for item in document.get("keys") or []:
            if str(item.get("key_id")) == str(retiring_key_id):
                old = item
                break
        if old is None:
            raise TrustStoreError("unknown retiring key %r" % retiring_key_id)
        if str(old.get("status")) != STATUS_ACTIVE:
            raise TrustStoreError("only ACTIVE keys can be rotated (key %r is %s)"
                                  % (retiring_key_id, old.get("status")))
        new_key_id = derive_key_id(new_public_key_b64)
        for item in document.get("keys") or []:
            if str(item.get("key_id")) == new_key_id:
                raise TrustStoreError("new key_id %r already exists" % new_key_id)
        old["status"] = STATUS_RETIRED
        old.setdefault("status_history", []).append(
            {"status": STATUS_RETIRED, "at": now_iso(), "source": "rotate",
             "reason": str(reason or "rotated")})
        document["keys"].append({
            "key_id": new_key_id,
            "public_key": str(new_public_key_b64),
            "algorithm": schema.ALGORITHM,
            "subject": str(new_subject),
            "scopes": [str(item) for item in new_scopes or []],
            "status": STATUS_ACTIVE,
            "created_at": now_iso(),
            "status_history": [{"status": STATUS_ACTIVE, "at": now_iso(),
                                "source": "rotate"}],
        })
        self._write_document(document)
        return {"retired": dict(old), "activated_key_id": new_key_id}
