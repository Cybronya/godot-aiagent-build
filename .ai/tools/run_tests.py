#!/usr/bin/env python3
"""Unified test runner for the project.

Discovers SceneTree test scripts (Features/*/test_*.gd + Tests/test_*.gd)
and runs each one headless:

    godot --headless --path . -s res://<path>

Test contract (established by existing tests): print PASS and exit 0 on
success; print FAIL and exit non-zero on failure.

Usage:
    python .ai/tools/run_tests.py                 # run all tests
    python .ai/tools/run_tests.py Tests           # only Tests/
    python .ai/tools/run_tests.py --stop-on-fail  # halt on first failure

Exit codes: 0 all passed; 1 any failure; 2 godot binary not found.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Candidate godot executables, relative to the parent of the project dir
# (layout: F:/Godot_v4.7-stable/{Godot*.exe, game/}).
GODOT_CANDIDATES = [
    PROJECT_ROOT.parent / "Godot_v4.7-stable_win64_console.exe",
    PROJECT_ROOT.parent / "Godot_v4.7-stable_win64.exe",
]

TIMEOUT_PER_TEST = 120


def find_godot() -> Path:
    for p in GODOT_CANDIDATES:
        if p.is_file():
            return p
    raise FileNotFoundError(
        "godot executable not found; looked at: "
        + ", ".join(str(p) for p in GODOT_CANDIDATES)
    )


def discover_tests(filter_dir: str | None = None) -> list[Path]:
    tests: list[Path] = []
    for pattern_dir in ("Features", "Tests"):
        base = PROJECT_ROOT / pattern_dir
        if not base.is_dir():
            continue
        tests.extend(sorted(base.glob("*/test_*.gd")))
        tests.extend(sorted(base.glob("test_*.gd")))
    if filter_dir:
        needle = filter_dir.replace("\\", "/").strip("/").lower()
        tests = [t for t in tests if needle in t.relative_to(PROJECT_ROOT).as_posix().lower()]
    return tests


def run_test(godot: Path, test: Path) -> tuple[bool, str]:
    res_path = "res://" + test.relative_to(PROJECT_ROOT).as_posix()
    cmd = [str(godot), "--headless", "--path", str(PROJECT_ROOT), "-s", res_path]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=TIMEOUT_PER_TEST, stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {TIMEOUT_PER_TEST}s"
    ok = proc.returncode == 0
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    tail = "\n".join((stdout + stderr).strip().splitlines()[-5:])
    return ok, f"exit={proc.returncode}" + (f"\n{tail}" if not ok else "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filter_dir", nargs="?", help="only run tests whose path contains this")
    parser.add_argument("--stop-on-fail", action="store_true")
    args = parser.parse_args()

    try:
        godot = find_godot()
    except FileNotFoundError as exc:
        print(f"[run_tests] FAIL: {exc}", file=sys.stderr)
        return 2

    tests = discover_tests(args.filter_dir)
    if not tests:
        print("[run_tests] no test scripts found")
        return 1

    print(f"[run_tests] {len(tests)} tests, godot={godot.name}")
    failures: list[str] = []
    for i, test in enumerate(tests, 1):
        rel = test.relative_to(PROJECT_ROOT).as_posix()
        ok, detail = run_test(godot, test)
        mark = "PASS" if ok else "FAIL"
        print(f"[{i}/{len(tests)}] {mark} {rel}" + (f"  ({detail})" if not ok else ""))
        if not ok:
            failures.append(rel)
            if args.stop_on_fail:
                break

    print(f"[run_tests] total={len(tests)} passed={len(tests) - len(failures)} failed={len(failures)}")
    if failures:
        print("[run_tests] failed tests:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("[run_tests] ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
