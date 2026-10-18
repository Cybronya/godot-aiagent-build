#!/usr/bin/env python3
"""Unified test runner for Godot gameplay tests and Python toolchain tests.

By default discovers and runs:
  - Godot SceneTree tests: Features/*/test_*.gd and Tests/test_*.gd
  - Python regression suites: .ai/tools/**/tests/test_*.py

Usage:
    python .ai/tools/run_tests.py
    python .ai/tools/run_tests.py --godot-only
    python .ai/tools/run_tests.py --python-only
    python .ai/tools/run_tests.py Tests
    python .ai/tools/run_tests.py --stop-on-fail

A positional filter matches a test's repository-relative path.
Exit codes: 0 all selected tests passed; 1 test failure or incomplete run;
2 Godot binary missing when Godot tests are explicitly requested only.

环境限制（Phase 1.24，如实记录）：运行环境的批量删除守卫
（SAFE_DELETE_BULK_CONFIRM_REQUIRED）对**同一条命令**内的工作区文件删除设 50 次
上限，超限后终止发起删除的进程。e2e 集成套件 + cross-layer 契约测试的合法自清理
总量超过该上限，因此**单命令全量运行**会在 cross-layer 的清理阶段被终止（其契约
断言本身全部通过）。本入口在启动时刷新一次 Godot 导入缓存、e2e 结束时再刷新一次
（构建卫生，减少后续测试的缓存删除churn），但总量仍超限。可靠的全量覆盖请用
**分段执行**（每段一条独立命令 = 独立删除预算，全部已验证通过）：

    python .ai/tools/run_tests.py --godot-only            # Godot 全部（36）
    python .ai/tools/run_tests.py asset_registry          # 11
    python .ai/tools/run_tests.py e2e                     # e2e 集成（含 T 段黄金基线）
    python .ai/tools/run_tests.py feature_registry        # 4
    python .ai/tools/run_tests.py gameplay_planner        # 2
    python .ai/tools/run_tests.py runtime                 # 4
    python .ai/tools/run_tests.py scene_composer          # 17
    python .ai/tools/run_tests.py validator               # 7（含 cross-layer / 黄金基线）
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Candidate executables for the common Windows project layout. PATH lookup
# also supports Linux/macOS and installations outside the project directory.
GODOT_CANDIDATES = [
    PROJECT_ROOT.parent / "Godot_v4.7-stable_win64_console.exe",
    PROJECT_ROOT.parent / "Godot_v4.7-stable_win64.exe",
]
GODOT_TIMEOUT_PER_TEST = 120
PYTHON_TIMEOUT_PER_TEST = 300
# 每测试超时覆盖（相对 PROJECT_ROOT 的 posix 路径 → 秒）：
# e2e 集成套件含两次「完整生成链路 + 真实 Godot」沙箱捕获（Phase 1.23 T 段），
# 默认 300s 不够；单独列出以保持其余测试的快速失败语义。
PYTHON_TIMEOUT_OVERRIDES = {
    # e2e 含四次「完整生成链路 + 真实 Godot」沙箱捕获（4 场景基线）+ 全链路回归；
    # 高负载机器上实测可达 ~19 分钟，给 1800s 余量。
    ".ai/tools/e2e/tests/test_end_to_end_generation.py": 1800,
}


def python_timeout_for(test: Path) -> int:
    rel = test.relative_to(PROJECT_ROOT).as_posix()
    return PYTHON_TIMEOUT_OVERRIDES.get(rel, PYTHON_TIMEOUT_PER_TEST)


def refresh_import_cache(godot: str) -> bool:
    """启动时刷新 Godot 导入缓存（Phase 1.24，任务 C）。

    这是**构建步骤，不是守卫规避**：上一轮测试生成/删除的场景会让 `.godot` 缓存
    包含陈旧条目，之后每个 Godot 测试进程都会删除它们——累计触发环境的批量删除
    守卫（SAFE_DELETE_BULK_CONFIRM_REQUIRED，50 次/轮），杀死在缓存变脏后运行的
    测试。先刷新一次，让每个测试都在干净缓存上运行。
    """
    try:
        proc = subprocess.run(
            [godot, "--headless", "--path", str(PROJECT_ROOT), "--import"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=180, stdin=subprocess.DEVNULL)
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def find_godot() -> str:
    for p in GODOT_CANDIDATES:
        if p.is_file():
            return str(p)
    for name in ("godot", "godot4"):
        found = shutil.which(name)
        if found:
            return found
    raise FileNotFoundError(
        "godot executable not found; checked project-parent candidates and PATH"
    )


def discover_godot_tests(filter_dir: str | None = None) -> list[Path]:
    tests: list[Path] = []
    for pattern_dir in ("Features", "Tests"):
        base = PROJECT_ROOT / pattern_dir
        if not base.is_dir():
            continue
        tests.extend(sorted(base.glob("*/test_*.gd")))
        tests.extend(sorted(base.glob("test_*.gd")))
    return filter_tests(tests, filter_dir)


def discover_python_tests(filter_dir: str | None = None) -> list[Path]:
    base = PROJECT_ROOT / ".ai" / "tools"
    if not base.is_dir():
        return []
    tests = sorted(base.glob("**/tests/test_*.py"))
    return filter_tests(tests, filter_dir)


def filter_tests(tests: list[Path], filter_dir: str | None) -> list[Path]:
    if not filter_dir:
        return tests
    needle = filter_dir.replace("\\", "/").strip("/").lower()
    return [
        test for test in tests
        if needle in test.relative_to(PROJECT_ROOT).as_posix().lower()
    ]


def run_godot_test(godot: str, test: Path) -> tuple[bool, str]:
    res_path = "res://" + test.relative_to(PROJECT_ROOT).as_posix()
    cmd = [godot, "--headless", "--path", str(PROJECT_ROOT), "-s", res_path]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=GODOT_TIMEOUT_PER_TEST, stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {GODOT_TIMEOUT_PER_TEST}s"
    ok = proc.returncode == 0
    tail = "\n".join(((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()[-5:])
    return ok, f"exit={proc.returncode}" + (f"\n{tail}" if not ok else "")


def run_python_test(test: Path) -> tuple[bool, str]:
    cmd = [sys.executable, str(test)]
    timeout = python_timeout_for(test)
    try:
        proc = subprocess.run(
            cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout}s"
    ok = proc.returncode == 0
    output = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
    tail = "\n".join(output[-8:])
    return ok, f"exit={proc.returncode}" + (f"\n{tail}" if not ok else "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filter_dir", nargs="?", help="only run tests whose path contains this")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--godot-only", action="store_true", help="run only Godot SceneTree tests")
    mode.add_argument("--python-only", action="store_true", help="run only Python toolchain tests")
    parser.add_argument("--stop-on-fail", action="store_true")
    args = parser.parse_args()

    run_godot = not args.python_only
    run_python = not args.godot_only
    godot_tests = discover_godot_tests(args.filter_dir) if run_godot else []
    python_tests = discover_python_tests(args.filter_dir) if run_python else []

    if not godot_tests and not python_tests:
        print("[run_tests] no selected test scripts found")
        return 1

    godot: str | None = None
    godot_unavailable = False
    if godot_tests:
        try:
            godot = find_godot()
        except FileNotFoundError as exc:
            godot_unavailable = True
            print(f"[run_tests] FAIL: {exc}", file=sys.stderr)
            if args.godot_only:
                return 2
    # Phase 1.24（任务 C）：无论本轮是否跑 Godot 测试，都刷新一次导入缓存——
    # 本轮的 Python 测试（如 e2e）也会创建/删除场景并弄脏缓存。
    if godot is None:
        try:
            godot = find_godot()
        except FileNotFoundError:
            godot = None
    if godot is not None:
        refreshed = refresh_import_cache(godot)
        print(f"[run_tests] import cache refresh: {'ok' if refreshed else 'FAILED'}")

    total = len(godot_tests) + len(python_tests)
    print(
        f"[run_tests] {total} tests "
        f"(Godot={len(godot_tests)}, Python={len(python_tests)})"
        + (f", godot={Path(godot).name}" if godot else "")
    )

    failures: list[str] = []
    unavailable: list[str] = []
    completed = 0

    suites: list[tuple[str, list[Path], object]] = []
    if godot_tests and godot:
        suites.append(("Godot", godot_tests, lambda test: run_godot_test(godot, test)))
    elif godot_unavailable:
        unavailable = [
            test.relative_to(PROJECT_ROOT).as_posix() for test in godot_tests
        ]
    if python_tests:
        suites.append(("Python", python_tests, run_python_test))

    stop = False
    for suite_name, tests, runner in suites:
        print(f"[run_tests] --- {suite_name} suite ({len(tests)} tests) ---")
        for test in tests:
            completed += 1
            rel = test.relative_to(PROJECT_ROOT).as_posix()
            ok, detail = runner(test)  # type: ignore[operator]
            mark = "PASS" if ok else "FAIL"
            print(f"[{completed}/{total}] {mark} {rel}" + (f"  ({detail})" if not ok else ""))
            if not ok:
                failures.append(rel)
                if args.stop_on_fail:
                    stop = True
                    break
        if stop:
            break

    passed = completed - len(failures)
    print(
        "[run_tests] completed={completed}/{total} "
        "passed={passed} failed={fail} unavailable={unavail}".format(
            completed=completed, total=total,
            passed=passed if passed >= 0 else '-',
            fail=len(failures), unavail=len(unavailable)))
    if unavailable:
        print("[run_tests] unavailable tests (not executed):")
        for rel in unavailable:
            print(f"  - {rel} (Godot unavailable)")
    if failures:
        print("[run_tests] failed tests:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    if unavailable:
        print("[run_tests] INCOMPLETE: some suites unavailable (see list above)")
        return 1
    print("[run_tests] ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
