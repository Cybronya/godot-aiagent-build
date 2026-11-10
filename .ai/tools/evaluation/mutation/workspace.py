#!/usr/bin/env python3
"""Mutation Workspace —— 隔离副本、路径守卫、仓库看守与受限清理（Phase 1.59）。

硬约束：

1. **仓库只读**：本模块从不写入 `Features/**`。所有 mutation 只作用于
   `.ai/tmp/p159/runs/<run>/Features` 这份**自己复制**出来的副本。
2. **路径必须落在项目内**：目标文件与副本目录都要经过 realpath 校验；
   符号链接一律拒绝（避免"指向仓库的链接"把写入带回真实实现）。
3. **清理只删自己的东西**：删除前必须同时满足「路径在 RUNS_ROOT 下」+
   「目录里有本次 run 的 ownership 标记」，否则拒绝删除。
4. **仓库看守**：运行前后各做一次 `Features/**` 的 sha256 快照，任何差异都要报告。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(os.path.dirname(_HERE))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_TOOLS))

FEATURES_DIR = os.path.join(PROJECT_ROOT, "Features")
RUNS_ROOT = os.path.join(PROJECT_ROOT, ".ai", "tmp", "p159", "runs")
OWNER_FILE = ".mutation-owner.json"


class WorkspaceError(Exception):
    """隔离/路径/清理前置条件不满足。"""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            return sha256_bytes(handle.read())
    except OSError:
        return ""


def real(path: str) -> str:
    return os.path.realpath(os.path.abspath(path))


def is_inside(path: str, root: str) -> bool:
    """realpath 级别的包含判断（`C:\\a\\b2` 不算在 `C:\\a\\b` 里）。"""
    target, base = real(path), real(root)
    try:
        return os.path.commonpath([target, base]) == base
    except ValueError:                                  # 不同盘符
        return False


def require_inside(path: str, root: str = PROJECT_ROOT, what: str = "path") -> str:
    if not is_inside(path, root):
        raise WorkspaceError("%s escapes %s: %s" % (what, root, path))
    return real(path)


def require_regular_file(path: str, root: str = PROJECT_ROOT) -> str:
    """存在、是普通文件、不是符号链接、且 realpath 仍在项目内。"""
    if os.path.islink(path):
        raise WorkspaceError("refusing to touch a symlink: %s" % path)
    if not os.path.isfile(path):
        raise WorkspaceError("file not found: %s" % path)
    require_inside(path, root, "target file")
    return real(path)


def snapshot(root: str) -> dict:
    """`relpath -> sha256` 快照（只读遍历，不跟随符号链接）。"""
    result = {}
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not os.path.islink(os.path.join(current, d)))
        for name in sorted(files):
            path = os.path.join(current, name)
            relative = os.path.relpath(path, root).replace("\\", "/")
            result[relative] = sha256_file(path)
    return result


def diff_snapshots(before: dict, after: dict) -> list:
    """列出新增/删除/改动的文件（用于证明"只改了目标文件"与"仓库未变"）。"""
    changes = []
    for name in sorted(set(before) | set(after)):
        old, new = before.get(name), after.get(name)
        if old == new:
            continue
        changes.append({"file": name,
                        "change": "added" if old is None else
                                  "removed" if new is None else "modified",
                        "before": old, "after": new})
    return changes


def create_run_dir(runs_root: str, mutation_id: str, run_id: str) -> str:
    root = os.path.join(runs_root, "%s-%s" % (mutation_id, run_id))
    os.makedirs(root, exist_ok=False)
    return root


def copy_features(run_root: str, run_id: str, mutation_id: str,
                  source: str = "") -> str:
    """把 `Features/` 复制进本次 run 目录；拒绝符号链接源。"""
    # 必须在 realpath 之前判断：realpath 会把符号链接解析掉，之后就看不出来了。
    if source and os.path.islink(os.path.abspath(source)):
        raise WorkspaceError("features source is a symlink: %s" % source)
    source = real(source or FEATURES_DIR)
    if not os.path.isdir(source):
        raise WorkspaceError("features dir not found: %s" % source)
    require_inside(source, PROJECT_ROOT, "features source")
    for current, dirs, files in os.walk(source, followlinks=False):
        for name in list(dirs) + list(files):
            if os.path.islink(os.path.join(current, name)):
                raise WorkspaceError("features source contains a symlink: %s"
                                     % os.path.join(current, name))
    destination = os.path.join(run_root, "Features")
    if os.path.exists(destination):
        raise WorkspaceError("run dir already contains Features: %s" % destination)
    shutil.copytree(source, destination, symlinks=False)
    marker = {"run_id": run_id, "mutation_id": mutation_id, "created_at": now_iso(),
              "source": os.path.relpath(source, PROJECT_ROOT).replace("\\", "/"),
              "owner": "evaluation/mutation"}
    with open(os.path.join(run_root, OWNER_FILE), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(marker, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return destination


def owns(run_root: str, run_id: str) -> bool:
    path = os.path.join(run_root, OWNER_FILE)
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8") as handle:
            marker = json.load(handle)
    except (OSError, ValueError):
        return False
    return marker.get("run_id") == run_id and marker.get("owner") == "evaluation/mutation"


def remove_run_dir(run_root: str, run_id: str, runs_root: str) -> dict:
    """只删除本次 Harness 创建、且带正确 ownership 标记的目录。"""
    if not is_inside(run_root, runs_root):
        return {"removed": False, "reason": "outside runs root: %s" % run_root}
    if not owns(run_root, run_id):
        return {"removed": False, "reason": "ownership marker missing or foreign"}
    shutil.rmtree(run_root, ignore_errors=True)
    return {"removed": not os.path.exists(run_root), "path": run_root}


def read_text(path: str) -> str:
    with open(path, "rb") as handle:
        return handle.read().decode("utf-8")


def write_text(path: str, text: str) -> None:
    with open(path, "wb") as handle:
        handle.write(text.encode("utf-8"))
