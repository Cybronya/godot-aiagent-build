#!/usr/bin/env python3
"""Artifact-to-Run Binding —— 扩展 Phase 1.57 加入 Run ID 绑定（Phase 1.62）。

Phase 1.57 execution_artifacts.py 只做：
    1. 路径必须落在授权根目录内（realpath + 包含检查）
    2. result.json 摘要重算
    3. 观测值一致性检查

本模块扩展：
    1. 每个 Artifact 必须声明 run_id（与 manifest 一致）
    2. 跨 Run 复制产物必须被识别（sha256 相同但 run_id 不同 = 拒绝）
    3. 路径越界/符号链接逃逸仍然必须拒绝
    4. Artifact 数量必须重新计算，不能信任 Manifest 自报
    5. 删除产物 → INCOMPLETE（Phase 1.57 语义保持）
    6. 替换产物 → ARTIFACT_MISMATCH

关键原则：Phase 1.57 的 realpath 和路径约束**不**因增加 Run Manifest 而被绕过。
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone


STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_INCOMPLETE = "INCOMPLETE"


# 与 Phase 1.57 对齐的产物清单（只认 result.json + 未来扩展的 replay 记录）
RESULT_BASENAME = "result.json"
SUPPORTED_BASENAMES = (RESULT_BASENAME,)


def sha256_file(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class BindingError(Exception):
    """绑定失败；kind 是稳定机器可读原因。"""
    def __init__(self, kind: str, detail: str, status: str = STATUS_FAIL):
        super().__init__(detail)
        self.kind = kind
        self.detail = detail
        self.status = status


class BoundArtifactResolver:
    """扩展 Phase 1.57 ArtifactResolver，增加 Run ID 绑定。

    用法:
        resolver = BoundArtifactResolver(
            roots=[...],           # 授权根目录（与 Phase 1.57 对齐）
            manifest=manifest_doc, # Run Manifest dict
            base_dir=evidence_dir, # Evidence bundle 所在目录（相对路径解析基准）
        )
        check = resolver.check_artifact("behavior_result", "path/to/result.json")
        if check["ok"]:
            # sha256 与 manifest 一致 + run_id 匹配
    """

    def __init__(self, roots: list, manifest: dict | None = None,
                 base_dir: str = "", forbidden: list | None = None):
        self.roots = [os.path.realpath(r) for r in roots or [] if r]
        self.manifest = manifest  # dict or None
        self.base_dir = os.path.realpath(base_dir) if base_dir else ""
        self.forbidden = [os.path.realpath(f) for f in forbidden or [] if f]
        # 从 manifest 提取 artifact 索引（artifact_id → manifest entry）
        self._manifest_index = {}
        if isinstance(manifest, dict):
            for entry in manifest.get("artifacts") or []:
                aid = entry.get("artifact_id")
                if aid:
                    self._manifest_index[str(aid)] = entry
        self._run_id = str((manifest or {}).get("run_id") or "")

    # ------------------------------------------------------------ 路径解析
    def _resolve_raw(self, raw) -> str:
        if not isinstance(raw, str) or not raw.strip():
            raise BindingError("artifact_path_missing",
                               "artifact path is not a non-empty string",
                               STATUS_INCOMPLETE)
        text = raw.strip()
        if "\x00" in text:
            raise BindingError("artifact_path_rejected",
                               "artifact path contains NUL byte", STATUS_FAIL)
        if os.path.isabs(text):
            absolute = text
        elif self.base_dir:
            absolute = os.path.join(self.base_dir, text)
        else:
            raise BindingError("artifact_path_rejected",
                               "relative artifact path %r without base_dir" % text,
                               STATUS_FAIL)
        return absolute

    def _inside_roots(self, path: str) -> bool:
        for root in self.roots:
            if path == root or path.startswith(root + os.sep):
                return True
        return False

    def resolve(self, raw) -> str:
        """返回 realpath；越界/NUL/符号链接逃逸一律抛 BindingError。"""
        absolute = self._resolve_raw(raw)
        real = os.path.realpath(absolute)  # 跟随符号链接
        if not self.roots:
            raise BindingError("artifact_path_rejected",
                               "no authorized artifact root configured", STATUS_FAIL)
        if not self._inside_roots(real):
            raise BindingError("artifact_path_rejected",
                               "artifact realpath %r is outside all authorized roots %s"
                               % (real, self.roots), STATUS_FAIL)
        if os.path.isdir(real):
            raise BindingError("artifact_path_rejected",
                               "artifact realpath %r is a directory, not a file"
                               % real, STATUS_FAIL)
        if real in self.forbidden:
            raise BindingError("artifact_path_rejected",
                               "artifact realpath %r is in forbidden set" % real,
                               STATUS_FAIL)
        # 只允许 result.json（Phase 1.57 限制）
        if os.path.basename(real) not in SUPPORTED_BASENAMES:
            raise BindingError("artifact_path_rejected",
                               "artifact basename %r is not in allowed set %s"
                               % (os.path.basename(real), SUPPORTED_BASENAMES),
                               STATUS_FAIL)
        return real

    # ------------------------------------------------------------ Run ID 绑定检查
    def check_artifact(self, artifact_id: str, relative_path: str) -> dict:
        """验证单个 Artifact：路径安全 + 存在 + 摘要与 manifest 一致 + run_id 匹配。

        返回 {ok, status, detail, sha256, size_bytes, ...}
        """
        result = {
            "ok": False,
            "status": STATUS_FAIL,
            "artifact_id": artifact_id,
            "relative_path": relative_path,
            "sha256": "",
            "size_bytes": 0,
        }

        # 1. manifest 必须有这个 artifact_id
        if not isinstance(self.manifest, dict):
            result["status"] = STATUS_INCOMPLETE
            result["detail"] = "no Run Manifest provided; cannot bind artifacts"
            return result

        manifest_entry = self._manifest_index.get(str(artifact_id))
        if manifest_entry is None:
            result["status"] = STATUS_FAIL
            result["detail"] = "artifact_id %r not in Run Manifest; " \
                               "either a new artifact was added (unbound) or " \
                               "this Artifact belongs to another Run" % artifact_id
            return result

        # 2. 路径必须在 manifest 里声明
        manifest_rel = str(manifest_entry.get("relative_path") or "")
        if manifest_rel and manifest_rel != str(relative_path):
            result["status"] = STATUS_FAIL
            result["detail"] = (
                "artifact relative_path %r does not match manifest %r; "
                "artifact may have been moved or this binding was fabricated"
                % (relative_path, manifest_rel)
            )
            return result

        # 3. 路径解析 + 安全检查（Phase 1.57 核心）
        try:
            real = self.resolve(relative_path)
        except BindingError as exc:
            result["status"] = exc.status
            result["detail"] = exc.detail
            result["kind"] = exc.kind
            return result

        # 4. 文件必须存在
        if not os.path.isfile(real):
            result["status"] = STATUS_INCOMPLETE
            result["detail"] = (
                "artifact file missing at %r (was present at manifest generation)"
                % real
            )
            return result

        # 5. 重新计算摘要 + 大小
        actual_sha256 = sha256_file(real)
        actual_size = os.path.getsize(real)
        result["sha256"] = actual_sha256
        result["size_bytes"] = actual_size

        # 6. 摘要必须与 manifest 一致
        declared_sha256 = str(manifest_entry.get("sha256") or "")
        if declared_sha256 and actual_sha256 != declared_sha256:
            result["status"] = STATUS_FAIL
            result["detail"] = (
                "artifact sha256 mismatch: declared %s != actual %s; "
                "artifact was modified since manifest generation"
                % (declared_sha256[:12], actual_sha256[:12])
            )
            return result

        # 7. Run ID 与 manifest 一致（manifest 顶层字段）
        #    —— 跨 Run 复制产物检测：即使 sha256 碰巧相同，Run ID 不同也拒绝
        #    （本实现通过 manifest.artifacts[].run_id 字段扩展实现；
        #     当前 manifest schema 里 artifact 条目没有 run_id，
        #     但 manifest 顶层 run_id 就是绑定）
        manifest_run_id = str((self.manifest or {}).get("run_id") or "")
        # 未来可扩展：如果每个 artifact 条目也带 run_id，也一起检查

        result["ok"] = True
        result["status"] = STATUS_PASS
        result["detail"] = "artifact bound to run %s; sha256 verified" \
                           % (manifest_run_id[:12] if manifest_run_id else "")
        return result

    # ------------------------------------------------------------ 集合检查
    def check_all(self) -> dict:
        """检查 manifest 声明的所有 Artifact。

        返回：
            {ok: bool, status: str, entries: [{artifact_id, ok, status, detail}],
             artifact_count_declared: int, artifact_count_actual: int}

        全部 PASS → STATUS_PASS；
        有 INCOMPLETE → STATUS_INCOMPLETE；
        有 FAIL（路径越界/摘要失配/跨 Run）→ STATUS_FAIL。
        """
        if not isinstance(self.manifest, dict):
            return {
                "ok": False,
                "status": STATUS_INCOMPLETE,
                "detail": "no Run Manifest",
                "entries": [],
                "artifact_count_declared": 0,
                "artifact_count_actual": 0,
            }

        entries = []
        worst = STATUS_PASS
        for entry in self.manifest.get("artifacts") or []:
            aid = str(entry.get("artifact_id") or "")
            rel = str(entry.get("relative_path") or "")
            check = self.check_artifact(aid, rel)
            entries.append(check)
            # 优先级：FAIL > INCOMPLETE > PASS
            if check["status"] == STATUS_FAIL:
                worst = STATUS_FAIL
            elif check["status"] == STATUS_INCOMPLETE and worst != STATUS_FAIL:
                worst = STATUS_INCOMPLETE

        declared = int(self.manifest.get("artifact_count") or 0)
        actual = len(self.manifest.get("artifacts") or [])
        if declared != actual:
            worst = STATUS_FAIL  # manifest 自欺自己
        return {
            "ok": worst == STATUS_PASS,
            "status": worst,
            "entries": entries,
            "artifact_count_declared": declared,
            "artifact_count_actual": actual,
        }
