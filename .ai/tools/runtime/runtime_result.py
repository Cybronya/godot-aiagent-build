#!/usr/bin/env python3
"""Runtime Result —— Runtime Playtest 的「结果」契约与落盘。

本模块是 Runtime Playtest 的第一层，只负责结果本身：

    - status 枚举（PASS / FAIL / TIMEOUT / CRASH）
    - runtime_result 数据结构、字段校验（契约见
      .ai/context/runtime_result_schema.yaml）
    - Runtime Playtest 契约读取（.ai/config/runtime-playtest.yaml）
    - Godot 可执行文件定位
    - 结果 / 原始日志读写

不负责：启动 Godot（run_scene.py）、解析输出（capture_output.py）、
诊断（diagnose_runtime.py）、修复（self_repair.py）。

用法（作为模块导入）:
    from runtime_result import build_result, load_contract, validate_result

架构约束：Runtime Runner 负责运行，Diagnosis 负责分析，Self Repair 负责修改；
本模块不属于任何 Feature / Scene / Validator。
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - 环境缺失依赖时明确失败
    print("FAIL: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

SCRIPT_DIR = Path(__file__).resolve().parent          # .ai/tools/runtime
TOOLS_DIR = SCRIPT_DIR.parent                          # .ai/tools
DOTAI_DIR = TOOLS_DIR.parent                           # .ai
REPO_ROOT = DOTAI_DIR.parent                           # 项目根（含 project.godot）

CONTRACT_PATH = DOTAI_DIR / "config" / "runtime-playtest.yaml"
RESULT_SCHEMA_PATH = DOTAI_DIR / "context" / "runtime_result_schema.yaml"

# ---------- status 契约 ----------

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_TIMEOUT = "TIMEOUT"
STATUS_CRASH = "CRASH"
STATUSES = (STATUS_PASS, STATUS_FAIL, STATUS_TIMEOUT, STATUS_CRASH)

# runtime_result 的必需字段（与 runtime_result_schema.yaml 保持一致）
RESULT_FIELDS = (
    "status",
    "exit_code",
    "duration",
    "scene",
    "stdout",
    "stderr",
    "errors",
    "warnings",
    "crash",
    "timeout",
)

# Runtime Playtest 契约的默认值（runtime-playtest.yaml 覆盖之）
DEFAULT_CONTRACT: dict[str, Any] = {
    "timeout": 30,
    "max_repair_attempts": 3,
    "fail_on_error": True,
    "fail_on_warning": False,
    "capture_output": True,
    "save_logs": True,
    "run_frames": 60,
    "godot_binary": "",
    "log_dir": ".ai/memory/runtime-logs",
    "history_dir": ".ai/memory/runtime-repairs",
}


# Self-Repair 安全策略默认值（runtime-playtest.yaml 的 repair_safety 节覆盖之）
DEFAULT_REPAIR_SAFETY: dict[str, Any] = {
    "allowed_targets": [
        "script_that_reported_the_error",
        "scene_under_playtest",
        "feature_that_owns_the_script",
    ],
    "max_files_per_attempt": 1,
    "allowed_change_kinds": ["replace_single_literal"],
    "forbidden_changes": [
        "delete_feature",
        "delete_scene",
        "modify_project_settings",
        "modify_ai_framework",
        "modify_skill_registry",
        "modify_validator",
        "modify_unrelated_feature",
        "modify_addons",
    ],
    "forbidden_path_prefixes": [".ai/", ".git/", "addons/", ".godot/"],
    "forbidden_paths": ["project.godot"],
    "require_revert": True,
}


def _load_yaml_block(section: str, path: str | os.PathLike | None, defaults: dict[str, Any]) -> dict[str, Any]:
    result = dict(defaults)
    target = Path(path) if path else CONTRACT_PATH
    if target.is_file():
        try:
            data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
        except Exception:
            return result
        block = data.get(section) if isinstance(data, dict) else None
        if isinstance(block, dict):
            for key, value in block.items():
                result[key] = value
    return result


def load_contract(path: str | os.PathLike | None = None) -> dict[str, Any]:
    """读取 Runtime Playtest 契约（runtime_playtest 节）；缺失时回退默认值。"""
    return _load_yaml_block("runtime_playtest", path, DEFAULT_CONTRACT)


def load_repair_safety(path: str | os.PathLike | None = None) -> dict[str, Any]:
    """读取 Self-Repair 安全策略（repair_safety 节）；缺失时回退默认值。"""
    return _load_yaml_block("repair_safety", path, DEFAULT_REPAIR_SAFETY)


# ---------- 项目 / Godot 定位 ----------


def find_project_root(start: str | os.PathLike | None = None) -> Path | None:
    """向上查找含 project.godot 的目录；找不到返回 None。"""
    current = Path(start).resolve() if start else Path.cwd().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "project.godot").is_file():
            return candidate
    return None


def _godot_candidates(project_root: Path | None, contract: dict[str, Any]) -> list[Path]:
    candidates: list[Path] = []
    env_bin = os.environ.get("GODOT_BIN", "").strip()
    if env_bin:
        candidates.append(Path(env_bin))
    configured = str(contract.get("godot_binary") or "").strip()
    if configured:
        candidates.append(Path(configured))
    # 项目相邻目录（本项目布局：F:/Godot_v4.7-stable/{Godot*.exe, game/}）
    for base in (project_root.parent if project_root else None, REPO_ROOT.parent):
        if base is None:
            continue
        candidates.extend(
            sorted(base.glob("Godot_v*_console.exe"))
            + sorted(base.glob("Godot_v*.exe"))
            + sorted(base.glob("Godot*_console.exe"))
            + sorted(base.glob("Godot*.exe"))
        )
    for name in ("godot4", "godot"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    seen: set[str] = set()
    unique: list[Path] = []
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def find_godot_binary(project_root: str | os.PathLike | None = None,
                      contract: dict[str, Any] | None = None) -> Path | None:
    """定位 Godot 可执行文件；优先 console 版本（可捕获输出）。"""
    root = find_project_root(project_root) if project_root else None
    for candidate in _godot_candidates(root, contract or load_contract()):
        if candidate.is_file():
            return candidate
    return None


# ---------- 结果构造 / 校验 ----------


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_result(status: str,
                 scene: str = "",
                 exit_code: int | None = None,
                 duration: float = 0.0,
                 stdout: str = "",
                 stderr: str = "",
                 errors: list | None = None,
                 warnings: list | None = None,
                 timeout: bool = False,
                 crash: bool = False,
                 command: list[str] | None = None,
                 project: str = "",
                 godot: str = "",
                 run_frames: int | None = None,
                 log_path: str = "",
                 playtest_note: str = "") -> dict[str, Any]:
    """构造 runtime_result（字段顺序即 schema 顺序）。"""
    return {
        "status": str(status),
        "exit_code": None if exit_code is None else int(exit_code),
        "duration": round(float(duration), 3),
        "scene": str(scene or ""),
        "stdout": stdout or "",
        "stderr": stderr or "",
        "errors": list(errors or []),
        "warnings": list(warnings or []),
        "crash": bool(crash),
        "timeout": bool(timeout),
        "command": list(command or []),
        "project": str(project or ""),
        "godot": str(godot or ""),
        "run_frames": run_frames,
        "log_path": str(log_path or ""),
        "playtest_note": str(playtest_note or ""),
        "timestamp": now_iso(),
    }


def validate_result(result: Any) -> list[str]:
    """校验 runtime_result 是否符合 schema 契约（只读，不修改）。"""
    errors: list[str] = []
    if not isinstance(result, dict):
        return ["runtime_result must be a mapping"]

    for field in RESULT_FIELDS:
        if field not in result:
            errors.append("runtime_result missing field: %s" % field)
    if errors:
        return errors

    status = result.get("status")
    if status not in STATUSES:
        errors.append("runtime_result.status must be one of %s, got %r" % (list(STATUSES), status))

    exit_code = result.get("exit_code")
    if exit_code is not None and not isinstance(exit_code, int):
        errors.append("runtime_result.exit_code must be an integer or null")
    duration = result.get("duration")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool):
        errors.append("runtime_result.duration must be a number")
    for field in ("scene", "stdout", "stderr"):
        if not isinstance(result.get(field), str):
            errors.append("runtime_result.%s must be a string" % field)
    for field in ("errors", "warnings"):
        if not isinstance(result.get(field), list):
            errors.append("runtime_result.%s must be a list" % field)
    for field in ("crash", "timeout"):
        if not isinstance(result.get(field), bool):
            errors.append("runtime_result.%s must be a boolean" % field)

    parsed_errors = result.get("errors") if isinstance(result.get("errors"), list) else []
    parsed_warnings = result.get("warnings") if isinstance(result.get("warnings"), list) else []

    # status 与观测事实必须自洽
    if status == STATUS_TIMEOUT and not result.get("timeout"):
        errors.append("runtime_result.status TIMEOUT requires timeout: true")
    if status == STATUS_CRASH and not result.get("crash"):
        errors.append("runtime_result.status CRASH requires crash: true")
    if status == STATUS_PASS:
        if result.get("timeout"):
            errors.append("runtime_result.status PASS contradicts timeout: true")
        if parsed_errors:
            errors.append("runtime_result.status PASS contradicts %d parsed error(s)" % len(parsed_errors))
    if status == STATUS_FAIL and not parsed_errors and not parsed_warnings:
        errors.append("runtime_result.status FAIL requires parsed errors or warnings")
    return errors


def result_signatures(result: dict) -> list[tuple]:
    """错误的稳定签名（用于判断修复是否让错误集合收敛）。"""
    signatures = []
    for entry in result.get("errors") or []:
        if not isinstance(entry, dict):
            continue
        signatures.append((
            str(entry.get("classification") or entry.get("type") or ""),
            str(entry.get("script") or ""),
            int(entry.get("line") or 0),
            " ".join(str(entry.get("message") or "").split()).lower(),
        ))
    return signatures


# ---------- 读写 ----------


def write_result(result: dict, path: str | os.PathLike) -> Path:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def read_result(path: str | os.PathLike) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_logs(result: dict, tag: str = "runtime",
              log_dir: str | os.PathLike | None = None) -> dict[str, str]:
    """保存原始输出日志（stdout / stderr / 结果快照）。返回写入路径。"""
    directory = Path(log_dir) if log_dir else (REPO_ROOT / DEFAULT_CONTRACT["log_dir"])
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = "%s-%s" % (tag, stamp)
    paths = {
        "stdout": directory / (base + ".stdout.log"),
        "stderr": directory / (base + ".stderr.log"),
        "result": directory / (base + ".json"),
    }
    paths["stdout"].write_text(result.get("stdout") or "", encoding="utf-8")
    paths["stderr"].write_text(result.get("stderr") or "", encoding="utf-8")
    paths["result"].write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {key: str(value) for key, value in paths.items()}


def summarize(result: dict) -> str:
    """一行摘要（CLI 输出用）。"""
    return "status=%s exit_code=%s errors=%d warnings=%d duration=%.2fs timeout=%s crash=%s" % (
        result.get("status"),
        result.get("exit_code"),
        len(result.get("errors") or []),
        len(result.get("warnings") or []),
        float(result.get("duration") or 0.0),
        bool(result.get("timeout")),
        bool(result.get("crash")),
    )
