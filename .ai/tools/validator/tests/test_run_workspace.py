#!/usr/bin/env python3
"""Run-workspace ownership tests（Phase 1.32 / F4）。

验证 `testsupport/run_workspace.py` 的所有权模型：

    W1  创建：token 唯一、运行根 / 账本存在且位于专属 base 内
    W2  正常清理：只删已登记文件并移除运行根
    W3  幂等：重复清理不报错、不重复删除
    W4  隔离：两个运行互不可见，A 清理不影响 B
    W5  内容被改写 ⇒ 拒绝删除（conflict）并保留证据
    W6  账本缺失 ⇒ 拒绝删除（fail-closed）
    W7  账本损坏（非法 JSON）⇒ 拒绝删除
    W8  账本路径越界（../）⇒ 拒绝，根外文件不受影响
    W9  符号链接 / 目录替换 ⇒ 拒绝删除，不跟随
    W10 未入账文件 ⇒ 不删运行根并报告 unaccounted    W11  异常退出后的残留：只报告、不自动删；显式 reclaim 需重新验证
    W12  两个真实子进程并发运行：互不删除对方产物
    W13  reclaim 拒绝非 token 目录
    W14  清理失败时保留账本等可诊断证据
    W16  删除前的再校验：摘要计算后文件被改动 ⇒ 拒绝（TOCTOU 缓解）
    W17  账本最后一行写到一半（记录被中断）⇒ 拒绝删除
    W18  运行标识冲突：同 token 的运行根已存在 ⇒ 拒绝接管
    W19  6 个 GDScript 测试已迁入每运行目录、不再写共享 Levels/user://（静态锁定）

全部在系统临时目录内运行，不触碰仓库资源；结束后检查无残留。
用法: python .ai/tools/validator/tests/test_run_workspace.py
退出码: 0 = 全部通过；1 = 有失败。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[2]              # .ai/tools
sys.path.insert(0, str(TOOLS_DIR))

import json                                                  # noqa: E402

from testsupport.run_workspace import (                      # noqa: E402
    LEGACY_TOKEN_RE,
    LEDGER_NAME,
    TOKEN_RE,
    RunWorkspace,
    is_within,
)
from testsupport import run_lock                             # noqa: E402

_failures: list[str] = []
_base: Path | None = None
_runs: Path | None = None


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + ((" | " + detail) if detail else ""))


def note(name: str, detail: str) -> None:
    # 注意：不打印 "SKIP:"——该标记会让 run_tests 把整个文件归为 INCOMPLETE。
    print("NOTE: %s (%s)" % (name, detail))


def _workspace() -> RunWorkspace:
    assert _runs is not None
    return RunWorkspace.create(base_dir=_runs)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _cleanup_quiet(workspace: RunWorkspace) -> None:
    """测试收尾：即使所有权拒绝删除，也只在专属临时 base 内强制移除。"""
    shutil.rmtree(workspace.run_root, ignore_errors=True)


def main() -> int:
    global _base, _runs
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    _base = Path(tempfile.mkdtemp(prefix="run_workspace_")).resolve()
    _runs = _base / "runs"
    _runs.mkdir()
    try:
        # ---------- W1：创建 ----------
        ws = _workspace()
        ok("W1: run token is pid + random suffix and the ledger is private to the run",
           bool(TOKEN_RE.match(ws.token)) and ws.token.startswith("%d-" % os.getpid())
           and ws.run_root.is_dir() and ws.ledger_path.is_file()
           and is_within(ws.run_root, _runs),
           repr((ws.token, str(ws.run_root))))
        _cleanup_quiet(ws)

        # ---------- W2：正常清理 ----------
        ws = _workspace()
        payload = ws.path_for("fixtures/a.json")
        _write(payload, '{"ok": true}')
        record = ws.record(payload)
        report = ws.cleanup()
        ok("W2: cleanup removes only recorded files and then the run root",
           report.run_root_removed and not ws.run_root.exists()
           and record.rel in report.removed and not report.failures(),
           repr(report))
        _cleanup_quiet(ws)

        # ---------- W3：幂等 ----------
        second = ws.cleanup()
        ok("W3: cleanup is idempotent after the run root is gone",
           not second.failures() and not second.run_root_removed,
           repr(second))

        # ---------- W4：两个运行隔离 ----------
        first, second_ws = _workspace(), _workspace()
        a_file = first.path_for("payload.txt")
        b_file = second_ws.path_for("payload.txt")
        _write(a_file, "A")
        first.record(a_file)
        _write(b_file, "B")
        second_ws.record(b_file)
        first_report = first.cleanup()
        ok("W4: cleaning run A leaves run B's resources untouched",
           first_report.run_root_removed and not first.run_root.exists()
           and b_file.is_file() and b_file.read_text(encoding="utf-8") == "B"
           and second_ws.run_root.is_dir(),
           repr((first_report, str(b_file))))
        second_report = second_ws.cleanup()
        ok("W4b: run B then cleans its own resources",
           second_report.run_root_removed and not second_ws.run_root.exists()
           and not second_report.failures(), repr(second_report))

        # ---------- W5：内容被改写 ----------
        ws = _workspace()
        payload = ws.path_for("payload.txt")
        _write(payload, "original")
        ws.record(payload)
        _write(payload, "tampered")
        report = ws.cleanup()
        ok("W5: a changed file is not deleted (conflict is reported)",
           payload.is_file() and bool(report.conflicts) and ws.run_root.is_dir()
           and any("conflict" in message for message in report.failures()),
           repr(report))
        _cleanup_quiet(ws)

        # ---------- W6：账本缺失 ----------
        ws = _workspace()
        payload = ws.path_for("payload.txt")
        _write(payload, "x")
        ws.record(payload)
        ws.ledger_path.unlink()
        report = ws.cleanup()
        ok("W6: a missing ledger refuses deletion (fail-closed)",
           payload.is_file() and "ledger" in report.ledger_error
           and not report.run_root_removed,
           repr(report))
        _cleanup_quiet(ws)

        # ---------- W7：账本损坏 ----------
        ws = _workspace()
        payload = ws.path_for("payload.txt")
        _write(payload, "x")
        ws.record(payload)
        with ws.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write("{not json\n")
        report = ws.cleanup()
        ok("W7: a corrupted ledger refuses deletion",
           payload.is_file() and "invalid JSON" in report.ledger_error
           and not report.run_root_removed,
           repr(report))
        _cleanup_quiet(ws)

        # ---------- W8：账本路径越界 ----------
        ws = _workspace()
        inside = ws.path_for("payload.txt")
        _write(inside, "in")
        ws.record(inside)
        escape = _base / "escape_target.txt"
        _write(escape, "outside")
        forged = {
            "event": "created", "token": ws.token, "path": "../escape_target.txt",
            "sha256": "a" * 64, "bytes": 7, "mtime_ns": 1,
        }
        import json as _json
        with ws.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(_json.dumps(forged) + "\n")
        report = ws.cleanup()
        ok("W8: a ledger path escaping the run root is refused, the outside file survives",
           escape.is_file() and escape.read_text(encoding="utf-8") == "outside"
           and bool(report.unsafe) and ws.run_root.is_dir(),
           repr(report))
        _cleanup_quiet(ws)

        # ---------- W9：符号链接 / 目录替换 ----------
        ws = _workspace()
        outside = _base / "symlink_target.txt"
        _write(outside, "target")
        payload = ws.path_for("payload.txt")
        _write(payload, "content")
        ws.record(payload)
        payload.unlink()
        try:
            os.symlink(outside, payload)
            symlink_ready = True
        except (OSError, NotImplementedError) as exc:
            symlink_ready = False
            note("W9 symlink check not exercised", str(exc))
        if symlink_ready:
            report = ws.cleanup()
            ok("W9: a symlink replacing a recorded file is refused and not followed",
               outside.is_file() and outside.read_text(encoding="utf-8") == "target"
               and bool(report.unsafe) and not report.run_root_removed,
               repr(report))
            payload.unlink()
            _write(payload, "content")                  # 还原为普通文件继续下一项
        else:
            _write(payload, "content")
        payload.unlink()
        payload.mkdir()
        report = ws.cleanup()
        ok("W9b: a directory replacing a recorded file is refused",
           payload.is_dir() and bool(report.incomplete) and not report.run_root_removed,
           repr(report))
        _cleanup_quiet(ws)

        # ---------- W10：未入账文件 ----------
        ws = _workspace()
        recorded = ws.path_for("recorded.txt")
        _write(recorded, "recorded")
        ws.record(recorded)
        stray = ws.path_for("stray.txt")
        _write(stray, "not in ledger")
        report = ws.cleanup()
        ok("W10: an unaccounted file blocks removal of the run root and is reported",
           stray.is_file() and not report.run_root_removed
           and report.unaccounted == ["stray.txt"]
           and ws.ledger_path.is_file(),
           repr(report))
        _cleanup_quiet(ws)

        # ---------- W11：异常退出后的残留（子进程不清理） ----------
        abandoned = _abandoned_workspace()
        keeper = _workspace()
        stale = keeper.stale_entries()
        stale_tokens = {entry["token"] for entry in stale}
        ok("W11: an abandoned run root is reported by a later run and not auto-deleted",
           abandoned.name in stale_tokens and abandoned.is_dir()
           and (abandoned / "payload.txt").is_file()
           and (abandoned / LEDGER_NAME).is_file(),
           repr(stale))
        refused = RunWorkspace.reclaim_abandoned(abandoned, acknowledge_abandoned=False)
        ok("W11b: reclaim without explicit acknowledgement is refused",
           abandoned.is_dir() and "acknowledge_abandoned" in refused.ledger_error,
           repr(refused))
        reclaimed = RunWorkspace.reclaim_abandoned(abandoned, acknowledge_abandoned=True)
        ok("W11c: explicit reclaim re-verifies the ledger and removes the abandoned root",
           reclaimed.run_root_removed and not abandoned.exists()
           and not reclaimed.failures(), repr(reclaimed))
        keeper.cleanup()

        # ---------- W12：两个真实子进程并发 ----------
        concurrent_ok, concurrent_detail = _concurrent_runs()
        ok("W12: two concurrent runs delete only their own resources",
           concurrent_ok, concurrent_detail)

        # ---------- W13：reclaim 拒绝非 token 目录 ----------
        assert _runs is not None
        impostor = _runs / "not-a-token"
        impostor.mkdir()
        (impostor / "payload.txt").write_text("x", encoding="utf-8")
        refused = RunWorkspace.reclaim_abandoned(impostor, acknowledge_abandoned=True)
        ok("W13: reclaim refuses a directory that is not a run token",
           impostor.is_dir() and bool(refused.unsafe), repr(refused))
        shutil.rmtree(impostor, ignore_errors=True)

        # ---------- W14：清理失败保留诊断证据 ----------
        ws = _workspace()
        payload = ws.path_for("payload.txt")
        _write(payload, "x")
        ws.record(payload)
        _write(payload, "changed")
        report = ws.cleanup()
        ledger_text = ws.ledger_path.read_text(encoding="utf-8")
        ok("W14: a refused cleanup keeps the ledger and the reported reasons",
           ws.ledger_path.is_file() and ws.run_root.is_dir()
           and "created" in ledger_text and bool(report.failures()),
           repr(report))
        _cleanup_quiet(ws)

        # ---------- W16：删除前的再校验（TOCTOU 缓解） ----------
        ws = _workspace()
        payload = ws.path_for("payload.txt")
        _write(payload, "stable")
        ws.record(payload)
        import testsupport.run_workspace as rw_module
        original_digest = rw_module.sha256_file

        def _digest_then_touch(path: Path) -> str:
            value = original_digest(path)
            os.utime(path, None)             # 摘要算完之后、删除之前文件被改动
            return value

        rw_module.sha256_file = _digest_then_touch
        try:
            report = ws.cleanup()
        finally:
            rw_module.sha256_file = original_digest
        ok("W16: a file changed after its digest was computed is refused "
           "(post-digest revalidation, not just a repeated path check)",
           payload.is_file() and bool(report.conflicts) and not report.run_root_removed,
           repr(report))
        _cleanup_quiet(ws)

        # ---------- W17：账本最后一行被中断 ----------
        ws = _workspace()
        payload = ws.path_for("payload.txt")
        _write(payload, "x")
        ws.record(payload)
        with ws.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write('{"event":"created","token":"')   # 记录写到一半进程中断
        report = ws.cleanup()
        ok("W17: a partially written ledger line (interrupted record) refuses deletion",
           payload.is_file() and "invalid JSON" in report.ledger_error
           and not report.run_root_removed, repr(report))
        _cleanup_quiet(ws)

        # ---------- W18：运行标识冲突 ----------
        import unittest.mock as _mock
        import testsupport.run_workspace as rw
        with _mock.patch.object(rw.uuid, "uuid4",
                                lambda: _mock.Mock(hex="cafef00d" * 4)):
            first = RunWorkspace.create(base_dir=_runs)
            first_root = first.run_root
            try:
                RunWorkspace.create(base_dir=_runs)
                collision_rejected = False
            except FileExistsError:
                collision_rejected = True
            _cleanup_quiet(first)
        ok("W18: a colliding run root is refused instead of being adopted "
           "(no takeover of an existing directory)",
           collision_rejected and not first_root.exists(),
           repr((collision_rejected, str(first_root))))

        # ---------- W19：GDScript 测试的迁移静态锁定 ----------
        repo_tests = Path(__file__).resolve().parents[4] / "Tests"
        migrated = [
            "test_generic_level_orchestration.gd", "test_level_orchestration.gd",
            "test_boss_orchestration.gd", "test_orchestration_trace.gd",
            "test_holdout_trace.gd", "test_waves_exit_gate.gd",
        ]
        offenders: list[str] = []
        missing: list[str] = []
        for name in migrated:
            source = (repo_tests / name).read_text(encoding="utf-8")
            if "res://Levels/E2e" in source or "res://Levels/.runs" in source:
                offenders.append(name)
            # Phase 1.35：运行根迁入 user://.test_runs/runs（token 作用域，C: 盘）；
            # 旧的仓库内 .ai/tmp/runs 基座与共享 user:// 根一律禁止。
            if '"user://.test_runs/runs"' not in source:
                missing.append(name + " (missing user://.test_runs/runs base)")
            if "res://.ai/tmp/runs" in source:
                offenders.append(name + " (in-repo run root)")
            if "_make_run_dir" not in source or "_owned" not in source:
                missing.append(name)
        ok("W19: the six GDScript tests use token-scoped user://.test_runs run roots"
           " and no longer write to shared Levels/ or in-repo roots",
           not offenders and not missing, repr((offenders, missing)))
    finally:
        if _base is not None:
            shutil.rmtree(_base, ignore_errors=True)
            ok("W15: the isolated test base is removed (no residue)",
               not _base.exists(), str(_base))

    # ==================== Phase 1.34（任务 B）：统一运行标识契约 ====================
    print()
    print("--- W20-W23: unified run identity contract (Phase 1.34) ---")
    _base = Path(tempfile.mkdtemp(prefix="run_ws_identity_"))
    try:
        ws_identity = RunWorkspace.create(base_dir=_base)
        ok("W20: Python tokens use the canonical <pid>-<16 hex> format"
           " (created and cleaned inside this check)",
           TOKEN_RE.match(ws_identity.token) is not None
           and ws_identity.token.split("-")[0] == str(os.getpid()),
           repr(ws_identity.token))
        RunWorkspace.create  # noqa: B018  (契约引用)
        assert ws_identity.cleanup().healthy()
        legacy = _base / "424242-deadbeef"                   # 旧格式：pid-<8 hex>
        legacy.mkdir()
        (legacy / "artifact.txt").write_text("legacy", encoding="utf-8")
        probe_ws = RunWorkspace(_base.parent, _base, "1-0000000000000000")
        stale = [entry for entry in probe_ws.stale_entries()
                 if entry["token"] == "424242-deadbeef"]
        ok("W21: a legacy-format run root is recognized but explicitly marked"
           " NOT reclaimable", len(stale) == 1
           and "legacy" in stale[0]["state"], repr(stale))
        report = RunWorkspace.reclaim_abandoned(legacy, acknowledge_abandoned=True)
        ok("W22: reclaim refuses a legacy-format run root (ownership not provable)",
           report.unsafe and not report.run_root_removed and legacy.exists(),
           repr(report.failures()[:2]))
        malformed = _base / "not-a-token-dir"
        malformed.mkdir()
        (malformed / "x.txt").write_text("x", encoding="utf-8")
        stale2 = [entry for entry in probe_ws.stale_entries()
                  if entry["token"] == "not-a-token-dir"]
        report2 = RunWorkspace.reclaim_abandoned(malformed, acknowledge_abandoned=True)
        ok("W23: malformed directory names are not treated as run roots"
           " (ignored by stale entries, refused by reclaim)",
           not stale2 and report2.unsafe and malformed.exists(), repr(stale2))
        cl_source = (Path(__file__).resolve().parents[4]
                     / ".ai" / "tools" / "validator" / "tests"
                     / "test_cross_layer_contract.py").read_text(encoding="utf-8")
        ok("W24: cross-layer fixtures live in the user:// test-runs base and the"
           " probe script stays res:// (deletion budget separation)",
           "godot_user_runs_base" in cl_source
           and 'user_res("fixtures/' in cl_source
           and 'probe_workspace.res_path("probe.gd")' in cl_source,
           repr((("godot_user_runs_base" in cl_source),
                 ('user_res("fixtures/' in cl_source),
                 ('probe_workspace.res_path("probe.gd")' in cl_source))))
    finally:
        shutil.rmtree(_base, ignore_errors=True)

    # ==================== Phase 1.34（任务 A）：e2e 串行锁 ====================
    print()
    print("--- L1-L7: e2e serial lock primitives (Phase 1.34) ---")
    _lock_base = Path(tempfile.mkdtemp(prefix="run_lock_"))
    try:
        lock_path = _lock_base / "e2e.lock"
        first = run_lock.acquire(lock_path, scope="e2e")
        ok("L1: a fresh lock is acquired and the holder record is written",
           first["status"] == "acquired" and lock_path.is_file()
           and first["holder"]["pid"] == os.getpid(), repr(first["message"]))
        second = run_lock.acquire(lock_path, scope="e2e")
        ok("L2: a second acquire while held is refused with holder info",
           second["status"] == "refused"
           and second["holder"]["pid"] == os.getpid()
           and "serial-only" in second["message"], repr(second["message"]))
        released = run_lock.release(lock_path, first["holder"])
        ok("L3: release by the holder removes the lock; the next acquire succeeds",
           released["status"] == "released" and not lock_path.exists()
           and run_lock.acquire(lock_path, scope="e2e")["status"] == "acquired")
        run_lock.release(lock_path, first["holder"])
        # 释放身份不匹配：不是本运行的锁 ⇒ 不删（fail-closed）
        other = run_lock.acquire(lock_path, scope="e2e")
        wrong = run_lock.release(lock_path, {"holder_id": "forged", "pid": 1,
                                             "scope": "e2e"})
        ok("L4: release with a mismatched holder record is refused (lock kept)",
           wrong["status"] == "kept" and lock_path.is_file(), repr(wrong))
        run_lock.release(lock_path, other["holder"])
        # 陈旧锁（持有者 pid 可证死亡）→ 回收并重建
        dead_pid = _find_dead_pid()
        stale_lock = json.dumps({"schema_version": 1, "pid": dead_pid,
                                 "holder_id": "gone", "host": "x", "scope": "e2e",
                                 "created_at": "2026-01-01T00:00:00+00:00"})
        lock_path.write_text(stale_lock + "\n", encoding="utf-8", newline="\n")
        reclaimed = run_lock.acquire(lock_path, scope="e2e")
        ok("L5: a lock whose holder pid provably no longer exists is reclaimed"
           " with a recorded reason",
           reclaimed["status"] == "reclaimed"
           and "no longer exists" in reclaimed["message"]
           and lock_path.is_file(), repr(reclaimed["message"]))
        run_lock.release(lock_path, reclaimed["holder"])
        # 锁内容非法 → fail-closed：拒绝 + 人工恢复说明
        lock_path.write_text("not json at all", encoding="utf-8", newline="\n")
        malformed = run_lock.acquire(lock_path, scope="e2e")
        ok("L6: a malformed lock file is refused with manual recovery"
           " instructions (fail-closed)",
           malformed["status"] == "refused"
           and "manual recovery" in malformed["message"]
           and lock_path.is_file(), repr(malformed["message"]))
        # 双真实子进程竞争：持锁者存活 ⇒ 对方明确拒绝；释放后可再获取
        child_source = (
            "import sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "import run_lock\n"
            "result = run_lock.acquire(sys.argv[2], scope=sys.argv[3])\n"
            "print(result['status'])\n"
            "print(result['message'])\n"
            "if result['status'] == 'acquired':\n"
            "    import time\n"
            "    time.sleep(3)\n"
            "    print(run_lock.release(sys.argv[2], result['holder'])['status'])\n"
        )
        lock_path.unlink(missing_ok=True)   # L6 按 fail-closed 保留了非法锁；
                                            # 这里清掉的是本测试自建的自有产物
        child_script = _lock_base / "lock_child.py"
        child_script.write_text(child_source, encoding="utf-8", newline="\n")
        holder_proc = subprocess.Popen(
            [sys.executable, str(child_script),
             str(TOOLS_DIR / "testsupport"), str(lock_path), "hold"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        time.sleep(1.5)                                       # 等子进程拿到锁
        contender = subprocess.run(
            [sys.executable, str(child_script),
             str(TOOLS_DIR / "testsupport"), str(lock_path), "contend"],
            capture_output=True, text=True, timeout=60)
        holder_out = holder_proc.communicate(timeout=60)[0]
        holder_lines = holder_out.splitlines()
        contender_lines = contender.stdout.splitlines()
        ok("L7: two real processes — the contender is refused while the holder"
           " is alive, and can acquire after release",
           holder_lines[0] == "acquired" and "released" in holder_lines
           and contender.returncode == 0
           and contender_lines[0] == "refused"
           and any("serial-only" in line for line in contender_lines),
           repr((holder_lines[:3], contender_lines[:2])))
        ok("L8: after the holder exits, the lock is free for the next run"
           " (verified by a fresh acquire)", 
           run_lock.acquire(lock_path, scope="e2e")["status"] == "acquired"
           and run_lock.release(lock_path,
                                json.loads(lock_path.read_text(encoding="utf-8"))
                                )["status"] == "released")
    finally:
        shutil.rmtree(_lock_base, ignore_errors=True)

    print()
    if _failures:
        print("FAIL: %d failing check(s)" % len(_failures))
        for failure in _failures:
            print("  - " + failure)
        return 1
    print("PASS: run workspace ownership (W1-W24, L1-L8)")
    return 0


def _find_dead_pid() -> int:
    """找一个当前不存在的 pid（用于构造"持有者可证死亡"的陈旧锁）。"""
    for candidate in range(4000000, 4000000 - 2000, -1):
        if not run_lock._pid_alive(candidate):
            return candidate
    raise RuntimeError("no dead pid found for the stale-lock test")


def _abandoned_workspace() -> Path:
    """子进程创建运行根、写入并登记后**不清理**退出（模拟异常终止）。"""
    assert _runs is not None
    script = (
        "import sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, %r)\n"
        "from testsupport.run_workspace import RunWorkspace\n"
        "ws = RunWorkspace.create(base_dir=Path(%r))\n"
        "p = ws.path_for('payload.txt')\n"
        "p.write_text('abandoned', encoding='utf-8')\n"
        "ws.record(p)\n"
        "print(str(ws.run_root))\n"
    ) % (str(TOOLS_DIR), str(_runs))
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=60,
                          stdin=subprocess.DEVNULL)
    lines = [line for line in (proc.stdout or "").splitlines() if line.strip()]
    if proc.returncode != 0 or not lines:
        raise RuntimeError("abandoned-workspace helper failed: %s"
                           % ((proc.stdout or "") + (proc.stderr or ""))[-500:])
    return Path(lines[-1].strip())


def _concurrent_runs() -> bool:
    """两个独立进程同时创建、登记、校验、清理各自的运行根。"""
    assert _runs is not None
    worker = (
        "import sys, time\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, %r)\n"
        "from testsupport.run_workspace import RunWorkspace\n"
        "base = Path(%r)\n"
        "ws = RunWorkspace.create(base_dir=base)\n"
        "payload = ws.path_for('payload.txt')\n"
        "payload.write_text(ws.token, encoding='utf-8')\n"
        "ws.record(payload)\n"
        "marker = base / ('ready_' + ws.token)\n"
        "marker.write_text('1', encoding='utf-8')\n"
        "deadline = time.time() + 20\n"
        "seen_other = False\n"
        "while time.time() < deadline:\n"
        "    others = [p for p in base.glob('ready_*') if p.name != 'ready_' + ws.token]\n"
        "    if others:\n"
        "        seen_other = True\n"
        "        break\n"
        "    time.sleep(0.02)\n"
        "time.sleep(0.2)\n"
        "own_ok = payload.is_file() and payload.read_text(encoding='utf-8') == ws.token\n"
        "report = ws.cleanup()\n"
        "ok = seen_other and own_ok and report.run_root_removed and not report.failures()\n"
        "print('WORKER:', ws.token, 'seen_other=', seen_other, 'own_ok=', own_ok,\n"
        "      'removed=', report.run_root_removed,\n"
        "      'failures=', report.failures())\n"
        "sys.exit(0 if ok else 1)\n"
    ) % (str(TOOLS_DIR), str(_runs))
    procs = [subprocess.Popen([sys.executable, "-c", worker],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8", errors="replace",
                              stdin=subprocess.DEVNULL)
             for _ in range(2)]
    outputs = []
    for proc in procs:
        out, _ = proc.communicate(timeout=90)
        outputs.append((proc.returncode, out or ""))
    for code, out in outputs:
        for line in out.splitlines():
            if line.startswith("WORKER:"):
                print("  " + line)
    for marker in _runs.glob("ready_*"):
        marker.unlink(missing_ok=True)
    leftovers = [p.name for p in _runs.iterdir() if p.is_dir()]
    return (all(code == 0 for code, _out in outputs) and not leftovers), repr(
        ([(code, out[-300:]) for code, out in outputs], leftovers))


if __name__ == "__main__":
    sys.exit(main())
