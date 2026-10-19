"""E2E serial-run lock（Phase 1.34 / 任务 A——L-9）。

e2e 的产物是共享目录中的**固定名文件**（`Scenes/<Pascal>.tscn` 是生产解析约定，
无法按运行拆分，见 PHASE_1_33_AUDIT §2.1），因此 e2e 只能安全串行。本模块提供
显式互斥锁：

- 获取：`O_CREAT | O_EXCL` 写锁文件（内容 = 持有者身份 JSON）。已存在 ⇒ 读取并
  校验持有者状态：存活 ⇒ 明确拒绝（带持有者信息）；**可证死亡** ⇒ 记录回收原因后
  重建；锁内容非法 / 无法读取 ⇒ fail-closed（拒绝 + 人工恢复说明）。
- 释放：只有锁内容与本运行登记的持有者身份**完全一致**时才删除；不一致 ⇒ 拒绝
  删除（不碰他人的锁）。
- 进程异常退出：锁残留（内含 pid）。下一次运行读取时若该 pid **已不存在**
  （Windows: OpenProcess 失败；POSIX: kill(pid,0) → ProcessLookupError），即可证明
  持有者死亡 ⇒ 自动回收（回收原因写入日志）。pid 被复用 ⇒ OpenProcess 成功 ⇒
  视为存活 ⇒ 拒绝（fail-closed）——绝不仅凭"锁文件过期"删除。
- 作用域：锁文件路径即作用域（默认 `.ai/tmp/runs/e2e.lock`）；不同 base_dir /
  不同工作目录互不影响。

已知的威胁模型边界（与 run_workspace 一致）：同权限攻击者伪造锁内容不在防线内；
`OpenProcess` 成功但持有者实际已退出（PID 复用）时按"存活"处理 ⇒ fail-closed。
"""

from __future__ import annotations

import ctypes
import json
import os
import platform
import uuid
from datetime import datetime, timezone
from pathlib import Path

LOCK_SCHEMA_VERSION = 1
_ERROR_INVALID_PARAMETER = 87
_STILL_ACTIVE = 259
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class LockError(RuntimeError):
    """锁的使用方式被违反（例如 release 与登记的持有者身份不一致）。"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _pid_alive(pid: int) -> bool:
    """探测进程是否存活；无法证明死亡时按存活处理（fail-closed 方向）。"""
    if platform.system() == "Windows":
        kernel32 = ctypes.windll.kernel32                # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(
            _PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            # ERROR_INVALID_PARAMETER = 该 pid 不存在任何进程 ⇒ 持有者已死亡
            return ctypes.GetLastError() != _ERROR_INVALID_PARAMETER
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True                              # 无法判定 ⇒ 按存活
            return exit_code.value == _STILL_ACTIVE       # 259 = 仍运行；其他 = 已退出
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return True
    return True


def _read_holder(lock_path: Path) -> tuple[dict | None, str]:
    try:
        text = lock_path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, "cannot read lock file (%s)" % exc
    try:
        holder = json.loads(text)
    except ValueError:
        return None, "lock file is not valid JSON"
    if not isinstance(holder, dict):
        return None, "lock file is not a JSON object"
    if holder.get("schema_version") != LOCK_SCHEMA_VERSION:
        return None, "lock file has an unsupported schema_version"
    for field in ("pid", "scope", "created_at", "holder_id"):
        if field not in holder:
            return None, "lock file is missing field %r" % field
    pid = holder.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return None, "lock file has an invalid pid"
    return holder, ""


def acquire(lock_path: Path, scope: str = "e2e") -> dict:
    """获取互斥锁。返回 {"status": "acquired"|"refused"|"reclaimed", ...}。

    - acquired：锁文件由本进程创建。
    - reclaimed：检测到**可证死亡**持有者的陈旧锁 → 记录回收原因 → 重新获取成功。
    - refused：持有者存活（或无法证明死亡）/ 锁内容非法 → 不动锁，人工恢复说明见
      message 字段。
    """
    lock_path = Path(lock_path)
    holder = {
        "schema_version": LOCK_SCHEMA_VERSION,
        "pid": os.getpid(),
        "holder_id": uuid.uuid4().hex,
        "host": platform.node(),
        "scope": scope,
        "created_at": _now(),
    }
    payload = json.dumps(holder, ensure_ascii=False, sort_keys=True)
    try:
        fd = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload + "\n")
        return {"status": "acquired", "holder": holder, "message": ""}
    existing, error = _read_holder(lock_path)
    if error:
        return {
            "status": "refused",
            "holder": None,
            "message": "stale-looking lock cannot be verified (%s); manual "
                       "recovery: verify no e2e process is running, then remove "
                       "%s by hand" % (error, lock_path),
        }
    live_pid = existing.get("pid")
    if isinstance(live_pid, int) and _pid_alive(live_pid):
        return {
            "status": "refused",
            "holder": existing,
            "message": "another e2e run holds the lock (pid=%s, scope=%r, "
                       "created_at=%s); e2e is serial-only" % (live_pid,
                       existing.get("scope"), existing.get("created_at")),
        }
    # 持有者可证死亡（pid 已无任何进程）→ 回收并重建。
    reclaim_reason = ("stale lock reclaimed: holder pid %s no longer exists"
                      % live_pid)
    try:
        lock_path.unlink()
    except OSError as exc:
        return {
            "status": "refused",
            "holder": existing,
            "message": "stale lock could not be removed (%s); manual recovery: "
                       "remove %s by hand" % (exc, lock_path),
        }
    try:
        fd = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return {
            "status": "refused",
            "holder": existing,
            "message": "lock was re-created between reclaim and re-acquire",
        }
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload + "\n")
    return {
        "status": "reclaimed",
        "holder": holder,
        "message": reclaim_reason,
        "reclaimed_holder": existing,
    }


def release(lock_path: Path, holder: dict) -> dict:
    """释放锁。只有锁内容与本运行登记的持有者身份**完全一致**时才删除。"""
    lock_path = Path(lock_path)
    if not lock_path.is_file():
        return {"status": "released", "message": "lock already absent"}
    existing, error = _read_holder(lock_path)
    if error:
        return {"status": "kept", "message": "not releasing: " + error}
    if not holder or existing.get("holder_id") != holder.get("holder_id") \
            or existing.get("pid") != holder.get("pid") \
            or existing.get("scope") != holder.get("scope"):
        return {
            "status": "kept",
            "message": "not releasing: lock content does not match this run's "
                       "holder record (fail-closed)",
        }
    try:
        lock_path.unlink()
    except OSError as exc:
        return {"status": "kept", "message": "cannot remove lock (%s)" % exc}
    return {"status": "released", "message": ""}
