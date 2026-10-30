#!/usr/bin/env python3
"""Test-runner evidence integrity unit/integration tests（Phase 1.29）。

审计结论 H1：`run_tests.py` 的分类只依据子进程退出码与失败标记，因此一个「报告了
`SKIP:` 但退出码为 0」的测试会被汇总成 PASS——即使它整段依赖（如 Godot）没有执行。
修复后 PASS 要求退出码为 0 **且**没有自报跳过；本文件锁定该语义，并走真实的
`run_python_test` 子进程路径验证（不只手测纯函数）。

用法: python .ai/tools/validator/tests/test_run_tests_evidence.py
退出码: 0 = 全部通过；1 = 有失败。
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

_TOOLS = Path(__file__).resolve().parents[2]              # .ai/tools
sys.path.insert(0, str(_TOOLS))

import run_tests                                           # noqa: E402

_failures: list[str] = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + ((" | " + detail) if detail else ""))


SKIP_OUTPUT = ("SKIP: G8: real Godot runtime playtest (godot executable not found)\n"
               "PASS: end-to-end generation integration test")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # ---------- E1：纯分类语义 ----------
    cases = [
        ("exit 0 without any skip evidence is PASS", 0, "PASS: suite", "", run_tests.STATUS_PASS),
        ("exit 0 that reported a skipped check is INCOMPLETE", 0, SKIP_OUTPUT, "",
         run_tests.STATUS_INCOMPLETE),
        ("a non-zero exit with a failure report stays FAIL even when a skip was reported",
         1, "FAIL: two checks failed\nSKIP: optional probe", "", run_tests.STATUS_FAIL),
        ("a non-zero exit that reported only skips is INCOMPLETE", 2, "SKIP: not inside a Godot project",
         "", run_tests.STATUS_INCOMPLETE),
        ("a non-zero exit without any report is INCOMPLETE (killed / no verdict)",
         137, "", "", run_tests.STATUS_INCOMPLETE),
        ("a timeout is INCOMPLETE regardless of output", 0, "PASS: suite",
         "TIMEOUT after 120s", run_tests.STATUS_INCOMPLETE),
    ]
    results = [(name, run_tests.classify(rc, out, timeout) == expected,
                run_tests.classify(rc, out, timeout)) for name, rc, out, timeout, expected in cases]
    ok("E1: the runner classifies PASS / FAIL / INCOMPLETE with skip evidence (Phase 1.29)",
       all(passed for _name, passed, _got in results),
       repr([(name, got) for name, passed, got in results if not passed]))

    ok("E2: reported skips are counted for the diagnostic (traceability of the verdict)",
       run_tests.skipped_checks(SKIP_OUTPUT) == 1
       and run_tests.skipped_checks("SKIP: a\nSKIP: b") == 2
       and run_tests.skipped_checks("PASS: x") == 0,
       repr(run_tests.skipped_checks(SKIP_OUTPUT)))

    # 分类常量本身是契约的一部分：PASS 之外的任何状态都必须使总入口非 0。
    ok("E3: only PASS is treated as success by the summary and exit code",
       run_tests.STATUS_PASS == "PASS"
       and {run_tests.STATUS_FAIL, run_tests.STATUS_INCOMPLETE}.isdisjoint({run_tests.STATUS_PASS}),
       repr((run_tests.STATUS_PASS, run_tests.STATUS_FAIL, run_tests.STATUS_INCOMPLETE)))

    # ---------- E4：真实子进程路径（不只手测纯函数） ----------
    # Phase 1.35：probe 目录放系统临时目录（默认）——run_python_test 按绝对路径
    # 直跑，无需仓库内路径；被杀运行也不在仓库根留下残留（原 PROJECT_ROOT 选址
    # 曾使全量 turn 的删除计数被推过环境守卫上限，见 PHASE_1_35_AUDIT §3）。
    work = Path(tempfile.mkdtemp(prefix="run_tests_evidence_"))
    probes = {
        "test_probe_clean.py": "print('PASS: clean probe')\nraise SystemExit(0)\n",
        "test_probe_skip.py": ("print('SKIP: optional probe (dependency unavailable)')\n"
                               "print('PASS: suite')\nraise SystemExit(0)\n"),
        "test_probe_fail.py": "print('FAIL: deliberate')\nraise SystemExit(1)\n",
        "test_probe_killed.py": "raise SystemExit(137)\n",
    }
    try:
        observed = {}
        for name, source in probes.items():
            path = work / name
            path.write_text(source, encoding="utf-8")
            observed[name] = run_tests.run_python_test(path)
        ok("E4a: a test that ran clean and exited 0 is PASS",
           observed["test_probe_clean.py"][0] == run_tests.STATUS_PASS,
           repr(observed["test_probe_clean.py"]))
        ok("E4b: a test that reported a skipped check is INCOMPLETE, not PASS"
           " (the golden-baseline section may not have run)",
           observed["test_probe_skip.py"][0] == run_tests.STATUS_INCOMPLETE
           and "skipped check" in observed["test_probe_skip.py"][1],
           repr(observed["test_probe_skip.py"]))
        ok("E4c: a test that reported a failure is FAIL (skip evidence cannot downgrade it)",
           observed["test_probe_fail.py"][0] == run_tests.STATUS_FAIL,
           repr(observed["test_probe_fail.py"]))
        ok("E4d: a test killed without any report is INCOMPLETE (never PASS)",
           observed["test_probe_killed.py"][0] == run_tests.STATUS_INCOMPLETE,
           repr(observed["test_probe_killed.py"]))
    finally:
        shutil.rmtree(work, ignore_errors=True)

    ok("E5: the classification probes left no residue in the project",
       not work.exists(), str(work))

    # ---------- E7：总入口本身（main）在“未执行任何测试”时必须非 0 ----------
    # 走真实 main() 决策路径（不是复述 classify）：选中 0 个测试不能返回成功。
    # --python-only + 不存在的过滤串 ⇒ 在任何 Godot 子进程之前就应返回 1。
    saved_argv = sys.argv
    sys.argv = ["run_tests.py", "--python-only", "zz_no_such_filter_phase_1_29"]
    try:
        no_tests_code = run_tests.main()
    finally:
        sys.argv = saved_argv
    ok("E7: the runner entry point returns non-zero when nothing was executed",
       no_tests_code == 1, "exit=%s" % no_tests_code)

    # ---------- E6：本入口自己的文档必须与实际语义一致 ----------
    doc = (run_tests.__doc__ or "")
    ok("E6: the runner documents that reported skips are INCOMPLETE (no silent PASS)",
       "SKIP" in doc and "INCOMPLETE" in doc and "PASS" in doc,
       doc[:120].replace("\n", " "))

    print()
    if _failures:
        for failure in _failures:
            print("FAIL: " + failure, file=sys.stderr)
        print("FAILED: %d check(s)" % len(_failures), file=sys.stderr)
        return 1
    print("PASS: test-runner evidence integrity (E1-E7)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
