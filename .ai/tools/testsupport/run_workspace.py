"""Per-run workspace with ownership-verified cleanup (Phase 1.32 / F4).

每次测试运行拥有一个 token（pid + 随机后缀）和一个专属运行根：

    <repo>/.ai/tmp/runs/<token>/          # 默认；测试可指定临时 base_dir
    <repo>/.ai/tmp/runs/<token>/ownership.jsonl

规则（fail-closed）：

- 删除只依据**账本**（`created` 事件），不按文件名前缀 / glob / mtime 推断。
- 删除前重新解析路径并校验：位于本运行根内、非符号链接、不是运行根本身。
- 删除前重算 sha256，并与写入时记录的 sha256 / size / mtime_ns 比对；
  内容或元数据变化 ⇒ 拒绝删除并报告（可能被其他运行或用户改写）。
- 账本缺失 / 不可解析 / 记录字段不完整 ⇒ 整次清理拒绝执行。
- 运行根只有在「所有文件都在账本中且已验证」时才递归删除。
- 异常退出遗留的运行根本模块**不会自动删除**；`detect_stale()` 只报告，
  `reclaim_abandoned()` 必须显式确认（acknowledge_abandoned=True）且重新验证账本。

该模块只依赖标准库；不驱动 Godot，可在临时目录中完整测试。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

LEDGER_NAME = "ownership.jsonl"
# Phase 1.34（任务 B）：统一运行标识契约。
#   canonical 格式 = "<pid>-<16 个小写十六进制>"（^[0-9]+-[0-9a-f]{16}$）：
#     Python 侧由 uuid4().hex[:16] 生成；GDScript 侧由 "%08x%08x" % [randi(), randi()]
#     生成。两侧同一语法、同一运行根命名规则（.ai/tmp/runs/<token>/）。
#   legacy 格式 = "<pid>-<8 个小写十六进制>"（Phase 1.32 Python / 1.33 GD 的旧格式）：
#     stale_entries() **只报告**（受限识别），reclaim_abandoned() **一律拒绝**——
#     旧格式不能仅凭匹配正则就当作可信所有权证明。
#   其余目录名（畸形）= 不是运行根：stale_entries 忽略，reclaim 拒绝。
# 「可识别运行根」「可证明所有权」「可安全回收」是三个不同条件：
#   可识别（格式匹配）⇒ 只报告；可证明所有权（canonical + 合法账本 + 摘要一致）⇒ 才可回收。
TOKEN_RE = re.compile(r"^[0-9]+-[0-9a-f]{16}$")
LEGACY_TOKEN_RE = re.compile(r"^[0-9]+-[0-9a-f]{8}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class OwnershipError(RuntimeError):
    """所有权模型被违反（账本损坏 / 路径越界 / 记录字段非法）。"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _norm(path: Path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def is_within(child: Path, root: Path) -> bool:
    """规范化后判断 child 是否位于 root 内（root 自身不算「内」）。"""
    child_n, root_n = _norm(child), _norm(root)
    return child_n.startswith(root_n + os.sep)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stat_key(stat_result: os.stat_result) -> tuple[int, int, int]:
    return (stat_result.st_size, stat_result.st_mtime_ns, stat_result.st_ino)


@dataclass
class Record:
    rel: str
    sha256: str
    size: int
    mtime_ns: int


@dataclass
class CleanupReport:
    removed: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    unsafe: list[str] = field(default_factory=list)
    incomplete: list[str] = field(default_factory=list)
    unaccounted: list[str] = field(default_factory=list)
    ledger_error: str = ""
    run_root_removed: bool = False
    run_root_kept_reason: str = ""
    ledger_kept: bool = False

    def failures(self) -> list[str]:
        messages: list[str] = []
        if self.ledger_error:
            messages.append("ledger: " + self.ledger_error)
        messages.extend("conflict (content/metadata changed): " + rel for rel in self.conflicts)
        messages.extend("unsafe path (outside run root or symlink): " + rel for rel in self.unsafe)
        messages.extend("unverifiable ownership record: " + rel for rel in self.incomplete)
        messages.extend("unaccounted file left in run root: " + rel for rel in self.unaccounted)
        if self.run_root_kept_reason and not self.run_root_removed:
            messages.append("run root kept: " + self.run_root_kept_reason)
        return messages

    def healthy(self) -> bool:
        return not self.failures()


class RunWorkspace:
    """一次测试运行的专属目录 + 所有权账本。"""

    def __init__(self, repo_root: Path, base_dir: Path, token: str) -> None:
        self.repo_root = Path(repo_root)
        self.base_dir = Path(base_dir)
        self.token = token
        self.run_root = self.base_dir / token
        self.ledger_path = self.run_root / LEDGER_NAME

    # ---------- 创建 ----------

    @classmethod
    def default_repo_root(cls) -> Path:
        # .ai/tools/testsupport/run_workspace.py -> repo root
        return Path(__file__).resolve().parents[3]

    @classmethod
    def default_base_dir(cls, repo_root: Path) -> Path:
        return Path(repo_root) / ".ai" / "tmp" / "runs"

    @classmethod
    def create(cls, repo_root: Path | None = None, base_dir: Path | None = None) -> "RunWorkspace":
        repo = Path(repo_root) if repo_root is not None else cls.default_repo_root()
        base = Path(base_dir) if base_dir is not None else cls.default_base_dir(repo)
        base.mkdir(parents=True, exist_ok=True)
        token = "%d-%s" % (os.getpid(), uuid.uuid4().hex[:16])
        workspace = cls(repo.resolve(), base.resolve(), token)
        # 运行根必须由本进程创建；已存在 = 名字冲突 / 他人目录 ⇒ 拒绝接管。
        workspace.run_root.mkdir(exist_ok=False)
        # 规范化（Windows 短名 / 大小写）后再建账本，保证路径比较使用同一形式。
        workspace.run_root = workspace.run_root.resolve()
        workspace.ledger_path = workspace.run_root / LEDGER_NAME
        # 账本用 O_EXCL 创建，保证「本运行的账本由本运行建立」。
        fd = os.open(str(workspace.ledger_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        return workspace

    # ---------- 路径 ----------

    def path_for(self, rel: str) -> Path:
        candidate = (self.run_root / rel).resolve()
        if not is_within(candidate, self.run_root):
            raise OwnershipError("path escapes run root: %r" % rel)
        return candidate

    def res_path(self, rel: str) -> str:
        path = self.path_for(rel)
        try:
            return "res://" + path.relative_to(self.repo_root.resolve()).as_posix()
        except ValueError as exc:  # pragma: no cover - 配置错误
            raise OwnershipError("run root is outside the repo: %s" % path) from exc

    def rel(self, path: Path) -> str:
        resolved = Path(path).resolve()
        if not is_within(resolved, self.run_root):
            raise OwnershipError("path outside run root: %s" % path)
        return resolved.relative_to(self.run_root.resolve()).as_posix()

    # ---------- 账本 ----------

    def _append(self, event: dict) -> None:
        line = json.dumps(event, ensure_ascii=False, sort_keys=True)
        with self.ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def record(self, path: Path) -> Record:
        """记录一个由本运行创建的文件（写入后调用）。"""
        if self.run_root.is_symlink():
            raise OwnershipError("run root became a symlink; refusing to record")
        target = Path(path)
        if target.is_symlink() or not target.is_file():
            raise OwnershipError("not a regular file: %s" % target)
        if not is_within(target.resolve(), self.run_root):
            raise OwnershipError("refusing to record a path outside the run root: %s" % target)
        digest = ""
        stat_result = None
        for _attempt in range(3):
            first = target.stat()
            digest = sha256_file(target)
            second = target.stat()
            if _stat_key(first) == _stat_key(second):
                stat_result = second
                break
        if stat_result is None:
            raise OwnershipError("file kept changing while recording: %s" % target)
        record = Record(rel=self.rel(target), sha256=digest,
                        size=stat_result.st_size, mtime_ns=stat_result.st_mtime_ns)
        self._append({
            "event": "created",
            "token": self.token,
            "path": record.rel,
            "sha256": record.sha256,
            "bytes": record.size,
            "mtime_ns": record.mtime_ns,
            "at": _now(),
        })
        return record

    def record_if_exists(self, path: Path) -> Record | None:
        """记录运行期间由工具链派生出的文件（例如 Godot 生成的 .uid）。"""
        if not Path(path).exists():
            return None
        return self.record(path)

    def _read_ledger(self) -> tuple[dict[str, Record], str]:
        if not self.ledger_path.is_file():
            return {}, "ownership ledger missing: %s" % self.ledger_path
        if self.ledger_path.is_symlink():
            return {}, "ownership ledger is a symlink: %s" % self.ledger_path
        records: dict[str, Record] = {}
        try:
            lines = self.ledger_path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            return {}, "cannot read ownership ledger (%s)" % exc
        for number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except ValueError:
                return {}, "invalid JSON at ledger line %d" % number
            if not isinstance(event, dict):
                return {}, "ledger line %d is not an object" % number
            if event.get("event") != "created":
                continue
            token = event.get("token")
            if token != self.token:
                return {}, "ledger line %d belongs to token %r, not %r" % (number, token, self.token)
            rel = event.get("path")
            digest = event.get("sha256")
            size = event.get("bytes")
            mtime_ns = event.get("mtime_ns")
            if not isinstance(rel, str) or not rel:
                return {}, "ledger line %d has no path" % number
            if not isinstance(digest, str) or not SHA256_RE.match(digest):
                return {}, "ledger line %d has an invalid sha256" % number
            if not isinstance(size, int) or size < 0:
                return {}, "ledger line %d has an invalid byte count" % number
            if not isinstance(mtime_ns, int):
                return {}, "ledger line %d has an invalid mtime_ns" % number
            records[rel] = Record(rel=rel, sha256=digest, size=size, mtime_ns=mtime_ns)
        return records, ""

    # ---------- 清理 ----------

    def cleanup(self) -> CleanupReport:
        report = CleanupReport()
        if not self.run_root.exists():
            return report                                  # 已清理：幂等成功
        if self.run_root.is_symlink():
            report.unsafe.append(str(self.run_root))
            report.run_root_kept_reason = "run root is a symlink"
            return report
        records, error = self._read_ledger()
        if error:
            report.ledger_error = error
            report.ledger_kept = True
            report.run_root_kept_reason = "ownership ledger unavailable"
            return report

        for rel, record in records.items():
            relative = Path(rel)
            if relative.is_absolute() or ".." in relative.parts:
                report.unsafe.append(rel)
                continue
            target = self.run_root / relative
            if not is_within(target, self.run_root):
                report.unsafe.append(rel)
                continue
            if target.is_symlink():
                report.unsafe.append(rel)
                continue
            if not target.exists():
                report.missing.append(rel)
                continue
            if not target.is_file():
                report.incomplete.append(rel + " (not a regular file)")
                continue
            try:
                before = target.lstat()
            except OSError:
                report.missing.append(rel)
                continue
            if (before.st_size, before.st_mtime_ns) != (record.size, record.mtime_ns):
                report.conflicts.append(rel + " (size/mtime differs from the ownership record)")
                continue
            digest = sha256_file(target)
            try:
                after = target.lstat()
            except OSError:
                report.missing.append(rel)
                continue
            if _stat_key(before) != _stat_key(after):
                report.conflicts.append(rel + " (file changed during verification)")
                continue
            if digest != record.sha256:
                report.conflicts.append(rel + " (sha256 differs from the ownership record)")
                continue
            try:
                target.unlink()
            except OSError as exc:
                report.incomplete.append("%s (%s)" % (rel, exc))
                continue
            report.removed.append(rel)
            self._append({"event": "removed", "token": self.token, "path": rel, "at": _now()})

        # 运行根只允许在「全部文件都已入账并验证」时递归删除。
        ledger_rel = self.ledger_path.relative_to(self.run_root).as_posix()
        unaccounted: list[str] = []
        for current, _dirs, files in os.walk(self.run_root):
            for name in files:
                rel = (Path(current) / name).relative_to(self.run_root).as_posix()
                if rel == ledger_rel:
                    continue
                if rel not in records:
                    unaccounted.append(rel)
        report.unaccounted = sorted(unaccounted)
        blocked = (report.ledger_error or report.conflicts or report.unsafe
                   or report.incomplete or report.unaccounted)
        if blocked:
            report.ledger_kept = True
            if not report.run_root_kept_reason:
                report.run_root_kept_reason = "unverified or unaccounted resources remain"
            return report

        try:
            shutil.rmtree(self.run_root)
        except OSError as exc:
            report.incomplete.append("run root (%s)" % exc)
            report.ledger_kept = True
            report.run_root_kept_reason = "cannot remove run root"
            return report
        report.run_root_removed = True
        return report

    # ---------- 残留发现 / 人工恢复 ----------

    def stale_entries(self) -> list[dict]:
        """列出 base_dir 下**其他**运行的目录（只读；绝不删除）。"""
        entries: list[dict] = []
        if not self.base_dir.is_dir():
            return entries
        for child in sorted(self.base_dir.iterdir()):
            if not child.is_dir() or child.name == self.token:
                continue
            if TOKEN_RE.match(child.name):
                pass                                               # canonical：正常报告
            elif LEGACY_TOKEN_RE.match(child.name):
                # legacy（Phase 1.32/1.33 旧格式）：受限识别——只报告，永不回收。
                entries.append({
                    "token": child.name,
                    "path": str(child),
                    "state": "legacy token format (recognized, NOT reclaimable)",
                    "last_event": "",
                    "file_count": sum(len(files) for _r, _d, files in os.walk(child)),
                })
                continue
            else:
                continue                                           # 畸形目录名：不是运行根
            ledger = child / LEDGER_NAME
            last_event = ""
            state = "no ledger"
            if ledger.is_file():
                try:
                    lines = [line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
                    last_event = lines[-1] if lines else ""
                    state = "ledger present"
                except OSError as exc:
                    state = "unreadable ledger (%s)" % exc
            entries.append({
                "token": child.name,
                "path": str(child),
                "state": state,
                "last_event": last_event,
                "file_count": sum(len(files) for _root, _dirs, files in os.walk(child)),
            })
        return entries

    @classmethod
    def reclaim_abandoned(cls, run_root: Path, *, acknowledge_abandoned: bool) -> CleanupReport:
        """显式回收一个**已确认被遗弃**的运行根（需人工/CI 明确确认）。

        仍然逐个验证：目录名 = token、父目录名为 runs、账本存在且可解析、
        目录内每个文件都在账本中且摘要一致、无符号链接。任何一项不成立即拒绝。
        """
        root = Path(run_root)
        report = CleanupReport()
        if not acknowledge_abandoned:
            report.ledger_error = "reclaim requires acknowledge_abandoned=True"
            return report
        if not root.exists():
            report.missing.append(str(root))
            return report
        if root.is_symlink() or not root.is_dir():
            report.unsafe.append(str(root))
            return report
        if root.parent.name != "runs" or not TOKEN_RE.match(root.name):
            if LEGACY_TOKEN_RE.match(root.name):
                report.unsafe.append(
                    str(root) + " (legacy token format: ownership is not provable,"
                    " manual recovery required)")
            else:
                report.unsafe.append(str(root))
            return report
        repo_root = root.parents[3] if len(root.parents) >= 4 else root.parent
        workspace = cls(repo_root, root.parent, root.name)
        records, error = workspace._read_ledger()
        if error:
            report.ledger_error = error
            return report
        ledger_rel = LEDGER_NAME
        for current, _dirs, files in os.walk(root):
            for name in files:
                rel = (Path(current) / name).relative_to(root).as_posix()
                if rel == ledger_rel:
                    continue
                target = Path(current) / name
                if target.is_symlink():
                    report.unsafe.append(rel)
                    continue
                record = records.get(rel)
                if record is None:
                    report.unaccounted.append(rel)
                    continue
                try:
                    stat_result = target.stat()
                    if (stat_result.st_size, stat_result.st_mtime_ns) != (record.size, record.mtime_ns):
                        report.conflicts.append(rel + " (size/mtime differs)")
                        continue
                    if sha256_file(target) != record.sha256:
                        report.conflicts.append(rel + " (sha256 differs)")
                except OSError as exc:
                    report.incomplete.append("%s (%s)" % (rel, exc))
        if report.unsafe or report.conflicts or report.incomplete or report.unaccounted:
            report.ledger_kept = True
            report.run_root_kept_reason = "unverified resources remain"
            return report
        try:
            shutil.rmtree(root)
        except OSError as exc:
            report.incomplete.append("run root (%s)" % exc)
            report.run_root_kept_reason = "cannot remove run root"
            return report
        report.run_root_removed = True
        report.removed = sorted(records)
        return report
