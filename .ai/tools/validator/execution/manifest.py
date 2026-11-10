#!/usr/bin/env python3
"""Run Manifest —— 一次执行的统一描述文件（Phase 1.62）。

Manifest 是 Execution Identity + 四种 Fingerprint + Artifact 清单 + Evidence 引用
的聚合体。用于 Execution Attestation 的签名消息载体。

关键原则：
    1. Manifest 的 SHA256 只是内容完整性标识，**不是**来源证明。
    2. 只有 Execution Attestation（可信主体签署）才具备来源证明能力。
    3. Manifest 采用确定性规范化序列化（sort_keys + 紧凑分隔符 + UTF-8）。
    4. Manifest 必须包含 Run ID 作为顶层字段（签名覆盖它）。
    5. Artifact 集合必须逐文件列出（不能只报数量）。
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

from .fingerprint import canonical_json, digest_document, sha256_hex


SCHEMA = "run_manifest"
SCHEMA_VERSION = 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonicalize_manifest(manifest: dict) -> bytes:
    """确定性规范化：整份 manifest（去掉 manifest_digest 字段）→ canonical JSON。

    manifest_digest 本身不进入规范化字节——否则自引用循环。
    """
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a dict")
    clean = {k: v for k, v in manifest.items() if k != "manifest_digest"}
    return canonical_json(clean)


def compute_manifest_digest(manifest: dict) -> str:
    return sha256_hex(canonicalize_manifest(manifest))


# ---------------------------------------------------------------- Artifact Manifest

SCHEMA_ARTIFACT = "artifact_manifest"
SCHEMA_ARTIFACT_VERSION = 1


def make_artifact_entry(artifact_id: str, artifact_type: str,
                         relative_path: str, *, sha256: str, size_bytes: int = 0,
                         media_type: str = "", created_at: str = "") -> dict:
    """单个 Artifact 的描述条目。"""
    return {
        "artifact_id": str(artifact_id),
        "artifact_type": str(artifact_type),
        "relative_path": str(relative_path),
        "sha256": str(sha256),
        "size_bytes": int(size_bytes or 0),
        "media_type": str(media_type or ""),
        "created_at": str(created_at or _now_iso()),
    }


def compute_artifact_set_digest(entries: list[dict]) -> str:
    """对 Artifact 集合生成摘要（排除 sha256 后的确定性清单）。

    摘要覆盖 artifact_id + artifact_type + relative_path + media_type，
    但**不**覆盖 sha256 本身——sha256 是 Artifact 内容的摘要，
    集合摘要描述的是"有哪些 Artifact"。Artifact 内容篡改通过
    重新计算每个 sha256 来检测。
    """
    # Windows/Python 不支持 set(dict) 排序——用 tuple of values 排序
    rows = []
    for e in entries:
        rows.append((
            str(e.get("artifact_id", "")),
            str(e.get("artifact_type", "")),
            str(e.get("relative_path", "")),
            str(e.get("media_type", "")),
        ))
    rows.sort()
    normalized = [
        {"artifact_id": r[0], "artifact_type": r[1],
         "relative_path": r[2], "media_type": r[3]}
        for r in rows
    ]
    return digest_document(normalized)


# ---------------------------------------------------------------- Run Manifest Builder

class RunManifest:
    """Run Manifest 构建器 + 校验器。

    用法:
        manifest = RunManifest(
            run_id=ident.run_id,
            execution_id=ident.execution_id,
            source_fingerprint=sources["source_fingerprint"],
            environment_fingerprint=sources["environment_fingerprint"],
            collector_fingerprint=sources["collector_fingerprint"],
            execution_config_fingerprint=sources["execution_config_fingerprint"],
            feature_id=ident.feature_id,
            behavior_id=ident.behavior_id,
            contract_version=ident.contract_version,
        )
        manifest.add_artifact(make_artifact_entry(...))
        manifest.complete(started_at=..., completed_at=..., execution_status="SUCCEEDED")
        doc = manifest.to_dict()
        digest = doc["manifest_digest"]
    """

    def __init__(self, *, run_id: str, execution_id: str,
                 source_fingerprint: str = "", environment_fingerprint: str = "",
                 collector_fingerprint: str = "",
                 execution_config_fingerprint: str = "",
                 feature_id: str = "", behavior_id: str = "",
                 scenario_id: str = "", contract_version: str = "",
                 started_at: str = "", completed_at: str = "",
                 execution_status: str = "", parent_run_id: str = "",
                 evidence_reference: str = ""):
        self.run_id = run_id
        self.execution_id = execution_id
        self.source_fingerprint = source_fingerprint
        self.environment_fingerprint = environment_fingerprint
        self.collector_fingerprint = collector_fingerprint
        self.execution_config_fingerprint = execution_config_fingerprint
        self.feature_id = feature_id
        self.behavior_id = behavior_id
        self.scenario_id = scenario_id
        self.contract_version = contract_version
        self.started_at = started_at
        self.completed_at = completed_at
        self.execution_status = execution_status
        self.parent_run_id = parent_run_id
        self.evidence_reference = evidence_reference
        self._artifacts: list[dict] = []

    def add_artifact(self, entry: dict) -> "RunManifest":
        """注册一个 Artifact（条目必须通过 make_artifact_entry 构建）。"""
        # 基本校验：不能空 artifact_id / artifact_type / relative_path / sha256
        for field in ("artifact_id", "artifact_type", "relative_path", "sha256"):
            if not str(entry.get(field) or ""):
                raise ValueError("artifact entry missing %r" % field)
        # 同一次执行里 artifact_id 必须唯一
        for existing in self._artifacts:
            if existing.get("artifact_id") == entry.get("artifact_id"):
                raise ValueError("duplicate artifact_id %r in manifest"
                                 % entry.get("artifact_id"))
        self._artifacts.append(dict(entry))
        return self

    def add_artifacts(self, entries: list[dict]) -> "RunManifest":
        for e in entries:
            self.add_artifact(e)
        return self

    def complete(self, *, started_at: str = "", completed_at: str = "",
                  execution_status: str = "") -> "RunManifest":
        """标记 Manifest 为完整（填入时间戳 + 状态）。"""
        if started_at:
            self.started_at = started_at
        if completed_at:
            self.completed_at = completed_at
        if execution_status:
            self.execution_status = execution_status
        return self

    def artifact_entries(self) -> list[dict]:
        return list(self._artifacts)

    def compute_artifact_set_digest(self) -> str:
        return compute_artifact_set_digest(self._artifacts)

    def to_dict(self) -> dict:
        doc = {
            "schema": SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "execution_id": self.execution_id,
            "source_fingerprint": self.source_fingerprint,
            "environment_fingerprint": self.environment_fingerprint,
            "collector_fingerprint": self.collector_fingerprint,
            "execution_config_fingerprint": self.execution_config_fingerprint,
            "feature_id": self.feature_id,
            "behavior_id": self.behavior_id,
            "scenario_id": self.scenario_id,
            "contract_version": self.contract_version,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "execution_status": self.execution_status,
            "parent_run_id": self.parent_run_id,
            "evidence_reference": self.evidence_reference,
            "artifact_set_digest": self.compute_artifact_set_digest(),
            "artifact_count": len(self._artifacts),
            "artifacts": self._artifacts,
            "generated_at": _now_iso(),
            "manifest_digest": "",  # 先占位，后面 compute_manifest_digest 重算
            "manifest_digest_scheme": "run-manifest-digest-v1",
        }
        doc["manifest_digest"] = compute_manifest_digest(doc)
        return doc

    # ------------------------------------------------------------ 校验

    @staticmethod
    def validate_manifest(manifest: dict) -> list:
        """返回错误列表。空列表 = 通过。"""
        errors = []
        if not isinstance(manifest, dict):
            return ["manifest must be a dict"]
        if manifest.get("schema") != SCHEMA:
            errors.append("manifest schema %r != %r"
                          % (manifest.get("schema"), SCHEMA))
            return errors
        if int(manifest.get("schema_version", 0)) != SCHEMA_VERSION:
            errors.append("manifest schema_version %r != %r"
                          % (manifest.get("schema_version"), SCHEMA_VERSION))
        # 顶层身份字段
        for field in ("run_id", "execution_id", "source_fingerprint",
                      "environment_fingerprint", "collector_fingerprint"):
            if not str(manifest.get(field) or ""):
                errors.append("manifest missing %r" % field)
        # run_id 必须是 UUIDv4
        from .identity import is_valid_uuidv4
        if not is_valid_uuidv4(manifest.get("run_id", "")):
            errors.append("run_id is not a valid UUIDv4")
        if not is_valid_uuidv4(manifest.get("execution_id", "")):
            errors.append("execution_id is not a valid UUIDv4")
        # manifest_digest 必须与内容一致（防篡改）
        declared_digest = manifest.get("manifest_digest", "")
        computed = compute_manifest_digest(manifest)
        if not declared_digest:
            errors.append("manifest_digest missing")
        elif declared_digest != computed:
            errors.append("manifest_digest mismatch: declared %s != computed %s"
                          % (declared_digest[:12], computed[:12]))
        # artifacts 必须是 list
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, list):
            errors.append("artifacts must be a list")
        else:
            seen_ids: set[str] = set()
            for idx, entry in enumerate(artifacts):
                if not isinstance(entry, dict):
                    errors.append("artifacts[%d] must be a dict" % idx)
                    continue
                for field in ("artifact_id", "artifact_type", "relative_path", "sha256"):
                    if not str(entry.get(field) or ""):
                        errors.append("artifacts[%d] missing %r" % (idx, field))
                aid = str(entry.get("artifact_id") or "")
                if aid in seen_ids:
                    errors.append("duplicate artifact_id %r" % aid)
                seen_ids.add(aid)
            # artifact_set_digest 必须与 artifacts 一致
            declared_set = manifest.get("artifact_set_digest", "")
            computed_set = compute_artifact_set_digest(artifacts)
            if declared_set and declared_set != computed_set:
                errors.append(
                    "artifact_set_digest mismatch: declared %s != computed %s"
                    % (declared_set[:12], computed_set[:12]))
            # artifact_count 不能自欺
            declared_count = int(manifest.get("artifact_count", 0))
            actual_count = len(artifacts)
            if declared_count != actual_count:
                errors.append(
                    "artifact_count %d != actual artifact entries %d"
                    % (declared_count, actual_count))
        return errors
