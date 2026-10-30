#!/usr/bin/env python3
"""Evaluation Runner —— 固定任务集的可重复执行入口（Phase 1.36）。

定位：把 `tasks.yaml` 里冻结的任务（输入、命令、断言、清理清单）执行成
**可审计的证据**，并按 `scoring.py` 的口径折叠成判定与指标。

设计约束（与任务书 §1/§3/§6 对齐）：

- 只读既有工具链：不新增生成器、不改 Feature、不改 Validator 判定。
- 全量证据：每个步骤记录 argv / 真实退出码 / 耗时 / 输出尾部；失败原因从证据读取，
  不写「预期通过」之类无法核对的字面结论。
- 未执行不等于通过：步骤未跑（前置失败、任务被跳过）一律 NOT_EXECUTED，
  且 `task_verdict` 只认必需阶段全 PASS。
- 所有权清理：只删「本次运行暂存 / 生成，且启动前不存在、内容标记匹配」的路径；
  标记不匹配即拒绝删除并使本次运行失败（fail-closed），绝不按目录/前缀递归清空。
- 可重复：每次运行在 `.ai/tmp/eval/<token>/` 下留独立证据目录（token 含 pid + uuid8），
  共享仓库目录（Scenes/Levels/Tests）在运行前后必须回到「任务声明之外零新增」。

用法：
    python .ai/tools/evaluation/runner.py --list
    python .ai/tools/evaluation/runner.py --task all
    python .ai/tools/evaluation/runner.py --task T1 T3
    python .ai/tools/evaluation/runner.py --task all --json --keep

退出码：0 = 全部任务 PASS 且清理无拒绝；1 = 有任务未通过或清理被拒绝；2 = 输入/环境错误。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
TOOLS_DIR = PROJECT_ROOT / ".ai" / "tools"
DEFAULT_TASKS = SCRIPT_DIR / "tasks.yaml"
DEFAULT_RUNS_DIRNAME = ".ai/tmp/eval"
BASELINE_FILES = (
    ".ai/tools/validator/baselines/holdout.json",
    ".ai/tools/validator/baselines/multi_stage_boss.json",
    ".ai/tools/validator/baselines/single_stage_boss.json",
    ".ai/tools/validator/baselines/waves.json",
)

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import scoring  # noqa: E402

try:
    import yaml
except ImportError:  # pragma: no cover - 环境缺依赖时给出可诊断输出
    print("FAIL: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)


# ---------------------------------------------------------------- 基础工具

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_snapshot() -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for rel in BASELINE_FILES:
        path = PROJECT_ROOT / rel
        if not path.is_file():
            snapshot[rel] = {"exists": False}
            continue
        stat = path.stat()
        snapshot[rel] = {
            "exists": True,
            "sha256": sha256_file(path),
            "mtime_ns": stat.st_mtime_ns,
        }
    return snapshot


def git_state() -> dict[str, Any]:
    def _git(*args: str) -> str:
        try:
            proc = subprocess.run(["git", *args], cwd=str(PROJECT_ROOT),
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=30)
        except (OSError, subprocess.SubprocessError) as exc:
            return "<error: %s>" % exc
        return (proc.stdout or "").strip()

    status = _git("status", "--porcelain=v1")
    lines = [line for line in status.splitlines() if line.strip()]
    return {
        "head": _git("rev-parse", "--short", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "modified": sum(1 for line in lines if not line.startswith("??")),
        "untracked": sum(1 for line in lines if line.startswith("??")),
        "staged": sum(1 for line in lines if line[:2].strip() and line[0] != "?"),
        "status_lines": len(lines),
    }


def find_godot() -> Path | None:
    for candidate in (PROJECT_ROOT.parent / "Godot_v4.7-stable_win64_console.exe",
                      PROJECT_ROOT.parent / "Godot_v4.7-stable_win64.exe"):
        if candidate.is_file():
            return candidate
    for name in ("godot", "godot4"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def godot_version(godot: Path) -> str:
    try:
        proc = subprocess.run([str(godot), "--version"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return "<error: %s>" % exc
    return (proc.stdout or proc.stderr or "").strip().splitlines()[0] if (proc.stdout or proc.stderr) else ""


def _replace_placeholders(value: str, ctx: dict[str, str]) -> str:
    text = value
    for key, replacement in ctx.items():
        text = text.replace("{%s}" % key, replacement)
    return text


def _resolve_path(text: str, ctx: dict[str, str]) -> Path:
    resolved = _replace_placeholders(text, ctx)
    path = Path(resolved)
    return path if path.is_absolute() else (PROJECT_ROOT / path)


def _resolve_argv(argv: list, ctx: dict[str, str]) -> list[str]:
    return [_replace_placeholders(str(item), ctx) for item in argv]


def _tail(text: str, limit: int = 1200) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return "..." + cleaned[-limit:]


# ---------------------------------------------------------------- JSON 断言

def resolve_json_path(document: Any, expression: str) -> Any:
    """极简 JSON 路径：`level.id` / `waves.length` / `waves[0].entries[0].count`。

    解析不到时抛 KeyError/IndexError —— 由调用方判为 FAIL，而不是当成 None 比较。
    """
    current = document
    for part in _json_path_tokens(expression):
        if isinstance(part, int):
            current = current[part]
        elif part == "length":
            current = len(current)
        else:
            current = current[part]
    return current


def _json_path_tokens(expression: str) -> list[Any]:
    """把 `a.b[0].c` 拆成 ['a','b',0,'c']；只支持这两类记号。"""
    token = ""
    index = 0
    parts: list[Any] = []
    while index < len(expression):
        char = expression[index]
        if char == ".":
            if token:
                parts.append(token)
                token = ""
        elif char == "[":
            if token:
                parts.append(token)
                token = ""
            end = expression.index("]", index)
            parts.append(int(expression[index + 1:end]))
            index = end
        else:
            token += char
        index += 1
    if token:
        parts.append(token)
    return parts


# ---------------------------------------------------------------- 步骤执行

class StepRunner:
    """在项目根运行一个步骤，返回证据字典（不抛异常）。"""

    def __init__(self, ctx: dict[str, str], godot: Path | None):
        self.ctx = ctx
        self.godot = godot

    def run(self, step: dict[str, Any]) -> dict[str, Any]:
        kind = str(step.get("kind") or "tool")
        step_id = str(step.get("id") or kind)
        started = time.time()
        record: dict[str, Any] = {
            "id": step_id,
            "phase": str(step.get("phase") or "artifacts"),
            "kind": kind,
        }
        try:
            if kind == "stage":
                self._stage(step, record)
            elif kind == "copy":
                self._copy(step, record)
            elif kind == "godot":
                self._godot(step, record)
            elif kind == "mutate_json":
                self._mutate_json(step, record)
            elif kind == "assert_json":
                self._assert_json(step, record)
            elif kind == "assert_file":
                self._assert_file(step, record)
            else:
                self._tool(step, record)
        except Exception as exc:  # 步骤级异常必须变成可读证据，而不是中断整次评估
            record.setdefault("detail", "")
            record["detail"] = (record["detail"] + " | exception: %r" % exc).strip(" |")
            record["status"] = scoring.STATUS_INCOMPLETE
        record["duration_s"] = round(time.time() - started, 3)
        if "status" not in record:
            record["status"] = self._judge(step, record)
        return record

    # ---------------------------------------------------------- 各类步骤

    def _stage(self, step: dict[str, Any], record: dict[str, Any]) -> None:
        fixture = SCRIPT_DIR / "fixtures" / str(step["fixture"])
        dest = _resolve_path(str(step["dest"]), self.ctx)
        record["dest"] = _relative(dest)
        if not fixture.is_file():
            record["status"] = scoring.STATUS_UNAVAILABLE
            record["detail"] = "missing fixture: %s" % fixture.name
            return
        if dest.exists():
            # 启动前就存在 ⇒ 归属不明，禁止接管/删除（fail-closed）
            record["status"] = scoring.STATUS_FAIL
            record["detail"] = "destination already exists before run: %s" % _relative(dest)
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fixture, dest)
        record["status"] = scoring.STATUS_PASS
        record["detail"] = "staged %s -> %s" % (fixture.name, _relative(dest))

    def _copy(self, step: dict[str, Any], record: dict[str, Any]) -> None:
        source = _resolve_path(str(step["source"]), self.ctx)
        dest = _resolve_path(str(step["dest"]), self.ctx)
        record["dest"] = _relative(dest)
        if not source.exists():
            record["status"] = scoring.STATUS_UNAVAILABLE
            record["detail"] = "missing source: %s" % _relative(source)
            return
        if dest.exists():
            record["status"] = scoring.STATUS_FAIL
            record["detail"] = "destination already exists before run: %s" % _relative(dest)
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, dest,
                            ignore=shutil.ignore_patterns(".godot", "__pycache__"))
        else:
            shutil.copy2(source, dest)
        record["status"] = scoring.STATUS_PASS
        record["detail"] = "copied %s -> %s" % (_relative(source), _relative(dest))

    def _mutate_json(self, step: dict[str, Any], record: dict[str, Any]) -> None:
        """受控负向变异体：复制文档后按 set 覆盖字段（只改声明的字段）。"""
        source = _resolve_path(str(step["source"]), self.ctx)
        dest = _resolve_path(str(step["dest"]), self.ctx)
        record["dest"] = _relative(dest)
        if not source.is_file():
            record["status"] = scoring.STATUS_UNAVAILABLE
            record["detail"] = "missing document: %s" % _relative(source)
            return
        if dest.exists():
            # 同一次运行内允许重写自己刚生成的变异体（幂等重跑）
            pass
        try:
            document = json.loads(source.read_text(encoding="utf-8"))
        except ValueError as exc:
            record["status"] = scoring.STATUS_FAIL
            record["detail"] = "invalid JSON: %r" % exc
            return
        for expression, value in (step.get("set") or {}).items():
            tokens = _json_path_tokens(str(expression))
            cursor = document
            for token in tokens[:-1]:
                cursor = cursor[token]
            cursor[tokens[-1]] = value
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        record["status"] = scoring.STATUS_PASS
        record["detail"] = "mutated %s -> %s" % (_relative(source), _relative(dest))

    def _tool(self, step: dict[str, Any], record: dict[str, Any]) -> None:
        argv = _resolve_argv(list(step.get("argv") or []), self.ctx)
        if not argv:
            record["status"] = scoring.STATUS_INCOMPLETE
            record["detail"] = "empty argv"
            return
        script = Path(argv[0])
        if not script.is_absolute():
            script = TOOLS_DIR / script
        cmd = [sys.executable, str(script), *argv[1:]]
        record["argv"] = [_relative(script), *argv[1:]]
        self._execute(cmd, step, record)

    def _godot(self, step: dict[str, Any], record: dict[str, Any]) -> None:
        if self.godot is None:
            record["status"] = scoring.STATUS_UNAVAILABLE
            record["detail"] = "godot binary not found"
            return
        argv = _resolve_argv(list(step.get("argv") or []), self.ctx)
        user_args = _resolve_argv(list(step.get("user_args") or []), self.ctx)
        cmd = [str(self.godot), "--headless", "--path", str(PROJECT_ROOT), *argv]
        if user_args:
            cmd.extend(["--", *user_args])
        record["argv"] = ["godot", *argv] + (["--", *user_args] if user_args else [])
        self._execute(cmd, step, record)

    def _execute(self, cmd: list[str], step: dict[str, Any], record: dict[str, Any]) -> None:
        # Godot 步骤默认更短的超时：探针挂住必须变成 INCOMPLETE 而不是拖垮整次评估
        default = 120 if record.get("kind") == "godot" else 300
        timeout = float(step.get("timeout") or default)
        try:
            proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
                                  timeout=timeout)
        except subprocess.TimeoutExpired:
            record["status"] = scoring.STATUS_INCOMPLETE
            record["detail"] = "timeout after %.0fs" % timeout
            return
        except OSError as exc:
            record["status"] = scoring.STATUS_UNAVAILABLE
            record["detail"] = "cannot execute: %r" % exc
            return
        record["exit"] = proc.returncode
        # 断言用**完整输出**（截断后的 tail 会漏掉长 JSON 里的关键行）；
        # 证据里只保留 tail，避免把整份日志塞进报告。
        record["_stdout"] = proc.stdout or ""
        record["_stderr"] = proc.stderr or ""
        record["stdout_tail"] = _tail(proc.stdout)
        record["stderr_tail"] = _tail(proc.stderr)

    def _assert_json(self, step: dict[str, Any], record: dict[str, Any]) -> None:
        path = _resolve_path(str(step["path"]), self.ctx)
        record["path"] = _relative(path)
        if not path.is_file():
            record["status"] = scoring.STATUS_FAIL
            record["detail"] = "missing document: %s" % _relative(path)
            return
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            record["status"] = scoring.STATUS_FAIL
            record["detail"] = "invalid JSON: %r" % exc
            return
        problems: list[str] = []
        observed: dict[str, Any] = {}
        for check in step.get("checks") or []:
            expression = str(check["path"])
            try:
                actual = resolve_json_path(document, expression)
            except (KeyError, IndexError, TypeError) as exc:
                problems.append("%s: path unresolved (%r)" % (expression, exc))
                continue
            observed[expression] = actual
            if "equals" in check and actual != check["equals"]:
                problems.append("%s: expected %r, got %r" % (expression, check["equals"], actual))
            if "contains" in check:
                text = actual if isinstance(actual, str) else json.dumps(actual, ensure_ascii=False)
                if str(check["contains"]) not in text:
                    problems.append("%s: %r not in %r" % (expression, check["contains"], text))
        record["observed"] = observed
        if problems:
            record["status"] = scoring.STATUS_FAIL
            record["detail"] = "; ".join(problems)
        else:
            record["status"] = scoring.STATUS_PASS

    def _assert_file(self, step: dict[str, Any], record: dict[str, Any]) -> None:
        problems: list[str] = []
        for rel in step.get("exists") or []:
            if not _resolve_path(str(rel), self.ctx).exists():
                problems.append("missing: %s" % rel)
        for rel in step.get("absent") or []:
            if _resolve_path(str(rel), self.ctx).exists():
                problems.append("should be absent: %s" % rel)
        for rel, needle in (step.get("contains_in") or {}).items():
            path = _resolve_path(str(rel), self.ctx)
            if not path.is_file():
                problems.append("missing: %s" % rel)
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if str(needle) not in text:
                problems.append("%s does not contain %r" % (rel, needle))
        for rel, needle in (step.get("not_contains_in") or {}).items():
            path = _resolve_path(str(rel), self.ctx)
            if not path.is_file():
                problems.append("missing: %s" % rel)
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if str(needle) in text:
                problems.append("%s still contains %r" % (rel, needle))
        if problems:
            record["status"] = scoring.STATUS_FAIL
            record["detail"] = "; ".join(problems)
        else:
            record["status"] = scoring.STATUS_PASS

    # ---------------------------------------------------------- 断言判定

    def _judge(self, step: dict[str, Any], record: dict[str, Any]) -> str:
        """对 `tool` / `godot` 步骤：先看退出码，再看 contains / missing 断言。"""
        if "exit" not in record:
            return scoring.STATUS_NOT_EXECUTED
        expected = int(step.get("expect_exit", 0))
        output = ((record.pop("_stdout", "") or "") + "\n"
                  + (record.pop("_stderr", "") or ""))
        if not output.strip():
            output = (record.get("stdout_tail") or "") + "\n" + (record.get("stderr_tail") or "")
        problems: list[str] = []
        if int(record["exit"]) != expected:
            problems.append("exit %d != expected %d" % (int(record["exit"]), expected))
        for needle in step.get("contains") or []:
            if str(needle) not in output:
                problems.append("output missing %r" % needle)
        for needle in step.get("missing") or []:
            if str(needle) in output:
                problems.append("output must not contain %r" % needle)
        if problems:
            record["detail"] = "; ".join(problems)
            return scoring.STATUS_FAIL
        return scoring.STATUS_PASS


def _rmtree(path: Path) -> None:
    """删除本次运行专属目录：只读文件先生成可写权限再重试（Windows 常见）。"""
    # Windows：Godot 会为缓存文件设只读位，先统一去掉再删
    for root, dirs, files in os.walk(path):
        for name in files:
            try:
                os.chmod(os.path.join(root, name), 0o600)
            except OSError:
                pass
        for name in dirs:
            try:
                os.chmod(os.path.join(root, name), 0o700)
            except OSError:
                pass

    def _retry(func, target, _exc_info):
        try:
            os.chmod(target, 0o700)
            func(target)
        except OSError:
            pass

    shutil.rmtree(path, onerror=_retry)


def _as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except (ValueError, OSError):
        return str(path)


# ---------------------------------------------------------------- 任务执行

class EvaluationRun:
    def __init__(self, run_dir: Path, config: dict[str, Any], json_mode: bool = False):
        self.run_dir = run_dir
        self.config = config
        self.json_mode = json_mode
        self.godot = find_godot()
        self.ledger: list[dict[str, Any]] = []
        self.cleanup_refused: list[str] = []
        self.cleanup_removed: list[str] = []
        self.uid_absent_before: set[str] = set()
        self.ctx = {
            "root": ".",
            "run_dir": _relative(run_dir),
            "run_abs": str(run_dir),
            "marker": str((config.get("run") or {}).get("artifact_marker") or "EVAL136"),
        }
        self.steps = StepRunner(self.ctx, self.godot)

    # ---------------------------------------------------------- 生命周期

    def preflight(self, tasks: list[dict[str, Any]]) -> dict[str, Any]:
        staging: list[dict[str, Any]] = []
        problems: list[str] = []
        for task in tasks:
            for step in task.get("stage") or []:
                dest = _resolve_path(str(step["dest"]), self.ctx)
                exists = dest.exists()
                staging.append({"task": task["id"], "dest": _relative(dest), "exists_before": exists})
                if exists:
                    problems.append("%s: %s already exists before run" % (task["id"], _relative(dest)))
        for raw in self._declared_paths(tasks):
            uid_rel = _relative(_resolve_path(raw, self.ctx)) + ".uid"
            if not (PROJECT_ROOT / uid_rel).exists():
                self.uid_absent_before.add(uid_rel)
        return {
            "godot": godot_version(self.godot) if self.godot else "<missing>",
            "godot_path": str(self.godot) if self.godot else "",
            "head": git_state(),
            "baselines_before": baseline_snapshot(),
            "staging": staging,
            "problems": problems,
        }

    def _declared_paths(self, tasks: list[dict[str, Any]]) -> list[str]:
        """静态可枚举的产物路径（stage dest + 步骤 generated）。"""
        paths: list[str] = []
        for task in tasks:
            for step in task.get("stage") or []:
                if step.get("dest"):
                    paths.append(str(step["dest"]))
            for group in ("attempts", "verify"):
                for attempt in task.get(group) or []:
                    steps = attempt.get("steps") if group == "attempts" else [attempt]
                    for step in steps or []:
                        for item in _as_list(step.get("generated")):
                            paths.append(str(item))
        return paths

    def _ledger_add(self, step: dict[str, Any], paths: list[str] | None = None) -> None:
        raw = _as_list(paths if paths is not None else step.get("generated"))
        marker = str(step.get("marker") or "")
        for item in raw:
            resolved = _replace_placeholders(str(item), self.ctx)
            self.ledger.append({"path": resolved, "marker": marker})

    def cleanup(self) -> dict[str, Any]:
        for entry in self.ledger:
            path = PROJECT_ROOT / entry["path"]
            if not path.exists():
                continue
            if path.is_dir():
                # 目录只在「位于本次运行专属目录内」时可递归删除；共享目录内的目录
                # 无法用内容标记证明归属 ⇒ 拒绝删除（fail-closed）
                if self.run_dir in path.parents:
                    _rmtree(path)
                    if path.exists():
                        self.cleanup_refused.append("%s (cannot remove staged directory)"
                                                    % entry["path"])
                    else:
                        self.cleanup_removed.append(entry["path"])
                else:
                    self.cleanup_refused.append("%s (directory outside run dir)" % entry["path"])
                continue
            declared = entry.get("marker") or ""
            if declared:
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    self.cleanup_refused.append("%s (unreadable: %s)" % (entry["path"], exc))
                    continue
                if declared not in text:
                    # 内容标记不匹配 ⇒ 无法证明这是本次运行的产物，拒绝删除
                    self.cleanup_refused.append("%s (marker %r missing)" % (entry["path"], declared))
                    continue
            try:
                path.unlink()
                self.cleanup_removed.append(entry["path"])
            except OSError as exc:
                self.cleanup_refused.append("%s (cannot remove: %s)" % (entry["path"], exc))
        # Godot 为脚本/场景衍生的 .uid：只在「源文件确实由本次运行创建」且
        # 「.uid 在运行前不存在」时删除，避免误删历史残留的 uid 映射
        removed_paths = set(self.cleanup_removed)
        for entry in self.ledger:
            if entry["path"] not in removed_paths:
                continue
            uid_path = entry["path"] + ".uid"
            if uid_path not in self.uid_absent_before:
                continue
            candidate = PROJECT_ROOT / uid_path
            if candidate.exists():
                try:
                    candidate.unlink()
                    self.cleanup_removed.append(uid_path)
                except OSError as exc:
                    self.cleanup_refused.append("%s (cannot remove: %s)" % (uid_path, exc))
        # 运行目录以 exist_ok=False 独占创建，其中的文件属于本次运行（含暂存副本）
        if self.run_dir.exists():
            for path in sorted(self.run_dir.iterdir()):
                if path.is_dir():
                    _rmtree(path)
                    if path.exists():
                        # 目录残留（例如 Godot 尚未释放的文件句柄）→ 不静默，记为拒绝
                        self.cleanup_refused.append("%s (run-dir subtree remains)"
                                                    % _relative(path))
                else:
                    path.unlink(missing_ok=True)
        return {
            "removed": self.cleanup_removed,
            "refused": self.cleanup_refused,
            "run_dir": _relative(self.run_dir),
            "unexpected": self._unexpected_leftovers(),
        }

    def _unexpected_leftovers(self) -> list[str]:
        marker = self.ctx["marker"]
        leftovers: list[str] = []
        for directory in ("Scenes", "Levels", "Tests"):
            base = PROJECT_ROOT / directory
            if not base.is_dir():
                continue
            for path in sorted(base.iterdir()):
                if not path.is_file():
                    continue
                if marker.lower() in path.name.lower() or "eval136" in path.name.lower():
                    leftovers.append(_relative(path))
        return leftovers

    # ---------------------------------------------------------- 任务

    def run_task(self, task: dict[str, Any]) -> dict[str, Any]:
        started = time.time()
        task_id = str(task["id"])
        record: dict[str, Any] = {
            "task_id": task_id,
            "title": str(task.get("title") or ""),
            "requirement": str(task.get("requirement") or ""),
            "covers": list(task.get("covers") or []),
            "required_phases": list(task.get("required_phases") or scoring.PHASES),
            "attempts": [],
            "steps": [],
        }

        # 1) 暂存输入（每个任务独立的共享目录路径，启动前必须不存在）
        stage_steps: list[dict[str, Any]] = []
        for step in task.get("stage") or []:
            result = self.steps.run(step)
            stage_steps.append(result)
            if result.get("status") == scoring.STATUS_PASS and step.get("dest"):
                self.ledger.append({
                    "path": _relative(_resolve_path(str(step["dest"]), self.ctx)),
                    "marker": str(step.get("marker") or ""),
                })
            if result.get("status") != scoring.STATUS_PASS:
                record["steps"].extend(stage_steps)
                record["verdict"] = scoring.STATUS_FAIL
                record["phases"] = scoring.summarize_phases(stage_steps)
                record["duration_s"] = round(time.time() - started, 3)
                return record

        # 2) 依次尝试：前一次未逐步骤全通过才继续下一次（attempt 语义见 tasks.yaml）
        decisive_steps: list[dict[str, Any]] = []
        attempt_steps_all: list[dict[str, Any]] = []
        for index, attempt in enumerate(task.get("attempts") or []):
            attempt_steps: list[dict[str, Any]] = []
            for step in attempt.get("steps") or []:
                result = self.steps.run(step)
                attempt_steps.append(result)
                if result.get("status") == scoring.STATUS_PASS:
                    self._ledger_add(step)
                if result.get("status") != scoring.STATUS_PASS:
                    break
            # `expect_failure: true` 的尝试是**证伪尝试**（例如先用最直接的
            # Entity Blueprint 试一次）：步骤按预期运行（包括预期中的非零退出码）
            # 不等于需求已满足，所以它永远不算通过，也不结束后续尝试。
            expect_failure = bool(attempt.get("expect_failure"))
            steps_as_expected = scoring.attempt_passed(attempt_steps)
            passed = steps_as_expected and not expect_failure
            record["attempts"].append({
                "name": str(attempt.get("name") or "attempt_%d" % (index + 1)),
                "kind": str(attempt.get("kind") or "initial"),
                "passed": passed,
                "expect_failure": expect_failure,
                "steps_as_expected": steps_as_expected,
                "steps": [step["id"] for step in attempt_steps],
                "statuses": {step["id"]: step.get("status") for step in attempt_steps},
                "details": {step["id"]: step.get("detail", "") for step in attempt_steps},
            })
            attempt_steps_all.extend(attempt_steps)
            if attempt_steps:
                decisive_steps = attempt_steps
            if passed:
                break

        # 3) 验证步骤（loadable / behavior / negative / regression）
        verify_steps = [self.steps.run(step) for step in task.get("verify") or []]
        for step, result in zip(task.get("verify") or [], verify_steps):
            if result.get("status") == scoring.STATUS_PASS:
                self._ledger_add(step)

        # 4) 阶段折叠：以「最终尝试 + 验证」为主证据；某个阶段在最终尝试里没有证据时，
        #    才向前一次尝试回退（例如需求→计划检查只存在于第一次尝试）。
        #    被后续尝试取代的阶段**不**回退，否则「修好之后仍然 FAIL」会被历史失败拖累。
        current_phases = scoring.summarize_phases(decisive_steps + verify_steps)
        earlier_steps = attempt_steps_all[:max(0, len(attempt_steps_all) - len(decisive_steps))]
        earlier_phases = scoring.summarize_phases(earlier_steps)
        phases: dict[str, dict[str, Any]] = {}
        for phase in set(current_phases) | set(earlier_phases):
            current = current_phases.get(phase) or {}
            if current.get("status") == scoring.STATUS_NOT_EXECUTED:
                phases[phase] = earlier_phases.get(phase) or current
            else:
                phases[phase] = current
        record["steps"] = stage_steps + attempt_steps_all + verify_steps
        record["phases"] = phases
        verdict = scoring.task_verdict(phases, record["required_phases"])
        record["verdict"] = verdict["status"]
        record["blocking"] = verdict["blocking"]
        attempts = record["attempts"]
        record["first_pass"] = bool(
            attempts and attempts[0].get("passed") and verdict["status"] == scoring.STATUS_PASS)
        record["duration_s"] = round(time.time() - started, 3)
        return record

    # ---------------------------------------------------------- 汇总

    def run(self, tasks: list[dict[str, Any]], human_interventions: int = 0) -> dict[str, Any]:
        started = time.time()
        preflight = self.preflight(tasks)
        results = []
        if preflight["problems"]:
            # 归属不明 ⇒ 不执行、不删除，直接判为不可执行
            for task in tasks:
                results.append({
                    "task_id": task["id"],
                    "title": task.get("title", ""),
                    "verdict": scoring.STATUS_FAIL,
                    "first_pass": False,
                    "phases": {},
                    "attempts": [],
                    "steps": [],
                    "duration_s": 0.0,
                    "blocking": preflight["problems"],
                })
        else:
            for task in tasks:
                results.append(self.run_task(task))
        cleanup = self.cleanup()
        after = baseline_snapshot()
        changed_baselines = [rel for rel, before in preflight["baselines_before"].items()
                             if after.get(rel) != before]
        metrics = scoring.compute_metrics(results, human_interventions=human_interventions)
        report = {
            "schema": {"id": "evaluation_report", "version": 1},
            "run": {
                "token": self.run_dir.name,
                "started": now_iso(),
                "duration_s": round(time.time() - started, 3),
                "godot": preflight["godot"],
                "git": preflight["head"],
                "tasks_file": _relative(DEFAULT_TASKS),
            },
            "baselines": {
                "before": preflight["baselines_before"],
                "after": after,
                "changed": changed_baselines,
            },
            "cleanup": cleanup,
            "tasks": results,
            "metrics": metrics,
            "limitations": [
                "任务集由评估者根据既有工具链的可行性先行探针后才冻结：本报告不是盲测，"
                "首次通过率只反映「该冻结流程在本次环境中是否一次通过」。",
                "generated 测试（scene_composer --tests）在根实例蓝图上断言为空，"
                "不能作为行为证据；行为证据只来自探针运行。",
                "模型调用/资源成本无法从仓库获得：cost 指标为 UNAVAILABLE。",
            ],
        }
        return report


# ---------------------------------------------------------------- CLI

def load_tasks(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("tasks"), list):
        raise SystemExit("FAIL: %s is not an evaluation task document" % path)
    return document


def print_summary(report: dict[str, Any]) -> None:
    print("Evaluation (%s)  tasks=%d  duration=%.1fs"
          % (report["run"]["token"], report["metrics"]["tasks_total"],
             report["run"]["duration_s"]))
    print("%-4s %-8s %-11s %s" % ("id", "verdict", "duration", "blocking"))
    for task in report["tasks"]:
        blocking = ",".join(task.get("blocking") or []) or "-"
        print("%-4s %-8s %8.1fs   %s"
              % (task["task_id"], task.get("verdict", "?"), task.get("duration_s", 0.0), blocking))
    phases = ("plan", "artifacts", "loadable", "behavior", "negative", "regression")
    print("\n%-4s %s" % ("id", "  ".join("%-13s" % p for p in phases)))
    for task in report["tasks"]:
        cells = []
        for phase in phases:
            info = (task.get("phases") or {}).get(phase) or {}
            cells.append("%-13s" % (info.get("status", "-")))
        print("%-4s %s" % (task["task_id"], "  ".join(cells)))
    metrics = report["metrics"]
    print("\nfirst_pass=%s  final_pass=%s" % (metrics["first_pass_rate"], metrics["final_pass_rate"]))
    print("auto_repair=%s  plan_revision=%s"
          % (metrics["auto_repair_success_rate"], metrics["plan_revision_success_rate"]))
    print("regression_defects=%s  human_interventions=%s"
          % (metrics["regression_defects"], metrics["human_interventions"]))
    changed = report["baselines"]["changed"]
    print("baselines_changed=%s  cleanup_refused=%s  leftovers=%s"
          % (changed, report["cleanup"]["refused"], report["cleanup"]["unexpected"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", nargs="*", default=["all"],
                        help="task ids to run (default: all)")
    parser.add_argument("--list", action="store_true", help="list tasks and exit")
    parser.add_argument("--tasks-file", default=str(DEFAULT_TASKS))
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS_DIRNAME)
    parser.add_argument("--human-interventions", type=int, default=0)
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("--keep", action="store_true",
                        help="keep the run directory (default: keep; evidence must be auditable)")
    args = parser.parse_args(argv)

    document = load_tasks(Path(args.tasks_file))
    tasks: list[dict[str, Any]] = document["tasks"]
    if args.list:
        for task in tasks:
            print("%-4s %-40s phases=%s" % (task["id"], task.get("title", ""),
                                            ",".join(task.get("required_phases") or [])))
        return 0

    wanted = [item.upper() for item in (args.task or ["all"])]
    if "ALL" not in wanted:
        known = {str(task["id"]).upper() for task in tasks}
        unknown = [item for item in wanted if item not in known]
        if unknown:
            print("FAIL: unknown task ids: %s" % ", ".join(unknown), file=sys.stderr)
            return 2
        tasks = [task for task in tasks if str(task["id"]).upper() in wanted]
    if not tasks:
        print("FAIL: no task selected", file=sys.stderr)
        return 2

    run_dir = PROJECT_ROOT / args.runs_dir / ("%d-%s" % (os.getpid(), uuid.uuid4().hex[:8]))
    run_dir.mkdir(parents=True, exist_ok=False)
    evaluation = EvaluationRun(run_dir, document)
    report = evaluation.run(tasks, human_interventions=args.human_interventions)
    (run_dir / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_summary(report)
        print("\nreport: %s" % _relative(run_dir / "report.json"))

    failed = [task["task_id"] for task in report["tasks"]
              if task.get("verdict") != scoring.STATUS_PASS]
    if failed or report["cleanup"]["refused"]:
        print("FAIL: %d task(s) not PASS: %s" % (len(failed), ", ".join(failed) or "-"),
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
