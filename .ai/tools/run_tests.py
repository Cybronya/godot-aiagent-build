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
    try:
        proc = subprocess.run(
            cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=PYTHON_TIMEOUT_PER_TEST,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {PYTHON_TIMEOUT_PER_TEST}s"
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
