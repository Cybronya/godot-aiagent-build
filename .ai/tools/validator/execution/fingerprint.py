#!/usr/bin/env python3
"""Execution Fingerprints —— Environment / Source / Collector / Config（Phase 1.62）。

四种独立指纹，不要合并成一个不可解释的摘要：

    environment_fingerprint      操作系统 + Python + Godot 运行环境
    source_fingerprint           项目代码来源（Git HEAD + 工作区摘要）
    collector_fingerprint        采集器代码来源（Python 模块 + GDScript 探针）
    execution_config_fingerprint  执行参数（Godot 启动参数 + Feature/Behavior 选择 + 超时）

每个指纹 = SHA256(canonical(json.dumps(normalized_dict)))
规范化规则：sort_keys=True, separators=(',', ':'), ensure_ascii=True

环境变化分级（来自配置，硬编码只列默认值）：
    INFORMATIONAL  可忽略（例：Python patch 版本变化）
    WARNING        影响可重复性但不致命（例：Godot 修订版本变化）
    INCOMPATIBLE   可能影响行为（例：Godot 小版本变化）
    INVALID        致命（例：Godot 主版本变化）

本模块**不**采集敏感环境变量（私钥、Token、密码、Cookie）。
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable


# ---------------------------------------------------------------- 规范化摘要

def canonical_json(data) -> bytes:
    """确定性规范化：sort_keys + 紧凑分隔符 + UTF-8。"""
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_document(data) -> str:
    """对任意可 JSON 序列化对象生成 SHA256 摘要（canonical 规范化）。"""
    return sha256_hex(canonical_json(data))


# ---------------------------------------------------------------- Environment

def _godot_console_path(project_root: str = "") -> str:
    """猜测 Godot 可执行路径（不依赖 GODOT_BIN 环境变量——那是用户覆盖）。"""
    # 先从已知路径尝试（Godot_v4.7-stable 目录下）
    candidates = [
        os.path.join(project_root, "..", "Godot_v4.7-stable_win64_console.exe"),
        os.path.join(project_root, "..", "Godot_v4.7-stable_win64.exe"),
        os.path.join(os.path.dirname(os.path.abspath(project_root or ".")),
                     "Godot_v4.7-stable_win64_console.exe"),
    ]
    for c in candidates:
        resolved = os.path.realpath(os.path.abspath(c))
        if os.path.isfile(resolved):
            return resolved
    # 环境变量
    env = os.environ.get("GODOT_BIN", "").strip()
    if env and os.path.isfile(env):
        return os.path.realpath(os.path.abspath(env))
    return ""


def _try_godot_version(godot_path: str) -> str:
    """尝试运行 godot --version 获取版本；失败返回空字符串。"""
    if not godot_path or not os.path.isfile(godot_path):
        return ""
    try:
        result = subprocess.run(
            [godot_path, "--version"],
            capture_output=True, text=True, timeout=15,
        )
        text = (result.stdout or result.stderr or "").strip()
        return text
    except Exception:
        return ""


def collect_environment(project_root: str = "") -> dict:
    """采集执行环境信息（系统 + Python + Godot）。

    不采集敏感环境变量（私钥、Token、密码）。
    """
    godot_path = _godot_console_path(project_root)
    godot_version = _try_godot_version(godot_path)
    doc = {
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "python_implementation": sys.implementation.name,
        "python_executable": os.path.realpath(sys.executable),
        "godot_path": godot_path,
        "godot_version": godot_version,
        "collector_module": "validator.execution.fingerprint",
        "collector_version": 1,
    }
    doc["fingerprint"] = digest_document({k: v for k, v in doc.items()
                                           if k != "fingerprint"})
    doc["fingerprint_scheme"] = "environment-fingerprint-v1"
    return doc


# ---------------------------------------------------------------- Source

def _git_head(project_root: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root or None, capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def _git_status_summary(project_root: str) -> dict:
    """采集工作区状态（不采集具体文件列表——避免噪声）。"""
    counts = {"modified": 0, "deleted": 0, "untracked": 0}
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_root or None, capture_output=True, text=True, timeout=15,
        )
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            status = line[:2].strip()
            if status.startswith("M"):
                counts["modified"] += 1
            elif status.startswith("D"):
                counts["deleted"] += 1
            elif status.startswith("??"):
                counts["untracked"] += 1
    except Exception:
        pass
    return counts


def collect_source(project_root: str = "") -> dict:
    """采集代码来源信息（Git HEAD + 工作区状态摘要）。"""
    doc = {
        "project_root": os.path.realpath(os.path.abspath(project_root or os.getcwd())),
        "git_head": _git_head(project_root),
        "git_status_counts": _git_status_summary(project_root),
        "collector_module": "validator.execution.fingerprint",
        "collector_version": 1,
    }
    doc["fingerprint"] = digest_document({k: v for k, v in doc.items()
                                           if k != "fingerprint"})
    doc["fingerprint_scheme"] = "source-fingerprint-v1"
    return doc


# ---------------------------------------------------------------- Collector

def _file_digest(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            return sha256_hex(handle.read())
    except OSError:
        return ""


def _collector_file_list(project_root: str) -> list[str]:
    """确定哪些文件属于采集器（确定性清单，不扫描整个 .ai/tools/）。

    采集器定义：feature_behavior_evidence 模块 + 其探针 GDScript。
    显式列出，不做文件系统递归（避免噪声目录被意外纳入）。
    """
    base = os.path.join(project_root, ".ai", "tools", "scene_composer")
    files = [
        os.path.join(base, "feature_behavior_evidence.py"),
        os.path.join(base, "composite_behavior_evidence.py"),
        os.path.join(base, "behavior_protocol.py"),
        os.path.join(base, "probes", "feature_behavior_probe.gd"),
        os.path.join(base, "probes", "composite_behavior_probe.gd"),
        os.path.join(base, "probes", "behavior_manifest.json"),
    ]
    return [os.path.realpath(p) for p in files if os.path.isfile(p)]


def collect_collector(project_root: str = "") -> dict:
    """采集采集器来源信息（代码摘要 + 依赖摘要）。"""
    file_paths = _collector_file_list(project_root)
    files_digest = {}
    for path in sorted(file_paths):
        rel = os.path.relpath(path, project_root) if project_root else os.path.basename(path)
        files_digest[rel] = _file_digest(path)

    # 依赖摘要（最小集合：Phase 1.40 采集器自身）
    dependency_digest = digest_document(sorted(files_digest.keys()))

    doc = {
        "collector_id": "feature_behavior_evidence",
        "collector_version": 1,
        "collector_schema_version": 1,
        "collector_entrypoint": "scene_composer.feature_behavior_evidence:verify_feature",
        "collector_source_files": files_digest,
        "collector_dependency_digest": dependency_digest,
        "collector_source_digest": digest_document(files_digest),
        "collector_level": "LOCAL_UNVERIFIED",  # 诚实声明：本阶段没有外部可信发布
    }
    doc["fingerprint"] = digest_document({k: v for k, v in doc.items()
                                           if k != "fingerprint"})
    doc["fingerprint_scheme"] = "collector-fingerprint-v1"
    return doc


# ---------------------------------------------------------------- Execution Config

def collect_execution_config(*, feature_id: str = "", behavior_id: str = "",
                              scenario_id: str = "", contract_version: str = "",
                              godot_args: dict | None = None,
                              replay_count: int = 2,
                              timeout_seconds: int = 120,
                              random_seed: str = "") -> dict:
    """采集执行参数指纹（影响执行结果的参数集合）。"""
    doc = {
        "feature_id": feature_id,
        "behavior_id": behavior_id,
        "scenario_id": scenario_id,
        "contract_version": contract_version,
        "godot_args": dict(godot_args or {}),
        "replay_count": int(replay_count),
        "timeout_seconds": int(timeout_seconds),
        "random_seed": random_seed,
    }
    doc["fingerprint"] = digest_document({k: v for k, v in doc.items()
                                           if k != "fingerprint"})
    doc["fingerprint_scheme"] = "execution-config-fingerprint-v1"
    return doc


# ---------------------------------------------------------------- 四级指纹打包

@dataclass
class ExecutionFingerprints:
    environment: dict
    source: dict
    collector: dict
    execution_config: dict

    def all_fingerprints(self) -> dict:
        return {
            "environment_fingerprint": self.environment.get("fingerprint", ""),
            "source_fingerprint": self.source.get("fingerprint", ""),
            "collector_fingerprint": self.collector.get("fingerprint", ""),
            "execution_config_fingerprint": self.execution_config.get("fingerprint", ""),
        }

    def to_dict(self) -> dict:
        return {
            "schema": "execution_fingerprints",
            "schema_version": 1,
            "environment": self.environment,
            "source": self.source,
            "collector": self.collector,
            "execution_config": self.execution_config,
            "fingerprint_set_digest": digest_document({
                "environment": self.environment.get("fingerprint", ""),
                "source": self.source.get("fingerprint", ""),
                "collector": self.collector.get("fingerprint", ""),
                "execution_config": self.execution_config.get("fingerprint", ""),
            }),
        }


def collect_all(project_root: str = "", *, feature_id: str = "",
                behavior_id: str = "", scenario_id: str = "",
                contract_version: str = "", godot_args: dict | None = None,
                replay_count: int = 2, timeout_seconds: int = 120,
                random_seed: str = "") -> ExecutionFingerprints:
    """一站式：采集四种独立指纹。"""
    return ExecutionFingerprints(
        environment=collect_environment(project_root),
        source=collect_source(project_root),
        collector=collect_collector(project_root),
        execution_config=collect_execution_config(
            feature_id=feature_id, behavior_id=behavior_id,
            scenario_id=scenario_id, contract_version=contract_version,
            godot_args=godot_args, replay_count=replay_count,
            timeout_seconds=timeout_seconds, random_seed=random_seed,
        ),
    )


# ---------------------------------------------------------------- 环境变化分级

# 简化实现——只定义分级函数的接口，实际分级逻辑可配置化扩展
# Phase 1.62 初版用"同 digest = 一致；不同 = 变化"
def classify_environment_change(old_digest: str, new_digest: str,
                                *, kind: str = "environment") -> str:
    """将环境变化按风险分级。

    返回 INFORMATIONAL / WARNING / INCOMPATIBLE / INVALID。
    初版：任何指纹变化都归类为 WARNING（不随意假设环境变化的风险等级）。
    """
    if not old_digest or not new_digest:
        return "INFORMATIONAL"
    if old_digest == new_digest:
        return "INFORMATIONAL"
    # 未来可根据 kind + 具体字段差异做更细粒度分类
    return "WARNING"


def recompute_fingerprint(document: dict, collector: Callable[[], dict]) -> str:
    """对一个已采集的指纹文档重新计算摘要（验证用）。"""
    if not isinstance(document, dict):
        return ""
    # 去掉 fingerprint 字段后重算
    clean = {k: v for k, v in document.items()
             if k not in ("fingerprint", "fingerprint_scheme")}
    return digest_document(clean)
