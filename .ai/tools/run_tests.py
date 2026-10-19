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

结果分类（Phase 1.26，报告真实状态而不把中断/
超时当成通过；Phase 1.29 补上「报告了 SKIP」）：
  PASS        实际执行且退出码 0，且**没有报告任何跳过（SKIP）的检查**
  FAIL        实际执行且退出码非 0，且输出里有失败报告（断言失败 / 契约不符 / 崩溃）
  INCOMPLETE  未执行、执行中断、超时、进程未给出任何报告即退出，或测试自报
              `SKIP: …`（依赖不可用 ⇒ 并非全部断言执行过）——无法确定结果

Phase 1.29 为何把 SKIP 归为 INCOMPLETE：本入口的 PASS 承诺是「实际执行过」；
测试自报 SKIP（例：godot executable not found ⇒ T 段黄金基线捕获/比较整段未跑）时
退出码仍为 0，若不单独识别，未执行的检查段会被汇总成 passed。与
validator/README 的「检查缺失永远不会被伪装成通过」保持一致。

Exit codes: 0 全部 PASS；1 存在 FAIL 或 INCOMPLETE（含 Godot 不可用）；
2 Godot binary missing when Godot tests are explicitly requested only.

环境观测（Phase 1.24 记录，**Phase 1.30 复核并更正**）：某些宿主运行时（WorkBuddy，
2026-10-17）对**同一条命令**内的工作区文件删除设 50 次上限，超限即终止发起删除的
进程（SAFE_DELETE_BULK_CONFIRM_REQUIRED）。该守卫**不在本仓库代码中**（仓库里只有
文档提到它）。当时 e2e 沙箱清理 + cross-layer 清理的合法删除总量超限，使单命令全量
在清理阶段被终止——契约断言本身已全部通过。

Phase 1.30 实测（Freebuff，2026-10-19）：该守卫**不存在**——单命令内 2000 次工作区
`unlink()` 不被终止，且 `python .ai/tools/run_tests.py` 单命令完成 **81/81 PASS（exit 0）**。
因此「单命令全量必被终止」是**宿主环境条件观测，不是本项目的固定限制**，不应作为
全量结果 INCOMPLETE 的默认解释。本入口在启动时刷新一次 Godot 导入缓存、e2e 结束时
再刷新一次（构建卫生，减少缓存删除 churn）。

被外部终止的进程仍以非 0 退出码、但没有失败报告结束 → 本入口将其归为
INCOMPLETE（不是 PASS），总入口返回 1。分段执行同样适用该分类：某段出现
INCOMPLETE 就不能宣称该段通过。在会触发删除守卫的宿主上，请用**分段执行**
（每段一条独立命令 = 独立删除预算）：

    python .ai/tools/run_tests.py --godot-only            # Godot 全部（38）
    python .ai/tools/run_tests.py asset_registry          # 11
    python .ai/tools/run_tests.py e2e                     # 1（e2e 集成；内部 171 项断言，含 T 段黄金基线）
    python .ai/tools/run_tests.py feature_registry        # 4
    python .ai/tools/run_tests.py gameplay_planner        # 2
    python .ai/tools/run_tests.py runtime                 # 4
    python .ai/tools/run_tests.py scene_composer          # 17
    python .ai/tools/run_tests.py validator               # 9（含 cross-layer / 黄金基线 / 入口证据完整性 /                                                           #    运行工作区所有权 W1–W19）

过滤按**路径子串**匹配（含文件名），段之间可能重叠（如 scene_composer 下名为
`*_validator*.py` 的文件同时落入 validator 段），因此各段计数之和不等于 Python 总数
（当前 44；全量 = Godot 38 + Python 44 = 82）。
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_INCOMPLETE = "INCOMPLETE"
# 测试自身报告失败时会写出的标记（用于区分「断言失败」与「未报告就死掉」）
FAILURE_MARKERS = ("FAIL", "FAILED", "Traceback", "SCRIPT ERROR")
# 测试自报跳过的标记（Phase 1.29）：出现即说明有检查没有执行，不能算作无条件 PASS。
SKIP_MARKERS = ("SKIP:",)

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


def skipped_checks(output: str) -> int:
    """测试自报的跳过条数（`SKIP:` 行数）；用于诊断与证据追溯。"""
    return sum(1 for marker in SKIP_MARKERS for _ in range(output.count(marker)))


def classify(returncode: int, output: str, timeout_label: str) -> str:
    """把一次执行归类为 PASS / FAIL / INCOMPLETE（只依据可观察证据）。

    Phase 1.29：PASS 要求退出码为 0 **且**没有自报 SKIP——测试报告了跳过的检查，就说明
    有断言没有执行（例：Godot 缺失时 T 段黄金基线捕获/比较整段跳过），不能汇总成 passed。
    非 0 退出仍以失败报告优先判 FAIL（断言失败不能被降级成「只是没跑全」）。
    """
    if timeout_label:
        return STATUS_INCOMPLETE
    if returncode == 0:
        return STATUS_INCOMPLETE if skipped_checks(output) else STATUS_PASS
    # 非 0 退出但完全没有失败报告 = 无法确定是断言失败还是被外部终止
    #（例如环境的批量删除守卫杀死进程）——记为 INCOMPLETE，两神都使总入口非 0。
    if not any(marker in output for marker in FAILURE_MARKERS):
        return STATUS_INCOMPLETE
    return STATUS_FAIL


def _detail_for(status: str, returncode: int, output: str, timeout_label: str) -> str:
    """非 PASS 结果的诊断行：带上退出码 / 超时与自报跳过条数（证据可追溯）。"""
    detail = timeout_label or f"exit={returncode}"
    skipped = skipped_checks(output)
    if status == STATUS_INCOMPLETE and skipped:
        detail += f"; reported {skipped} skipped check(s) (dependency unavailable?)"
    return detail



def run_godot_test(godot: str, test: Path) -> tuple[str, str]:
    res_path = "res://" + test.relative_to(PROJECT_ROOT).as_posix()
    cmd = [godot, "--headless", "--path", str(PROJECT_ROOT), "-s", res_path]
    timeout_label = ""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=GODOT_TIMEOUT_PER_TEST, stdin=subprocess.DEVNULL,
        )
        returncode, output = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        returncode, output = 1, ""
        timeout_label = f"TIMEOUT after {GODOT_TIMEOUT_PER_TEST}s"
    status = classify(returncode, output, timeout_label)
    tail = "\n".join(output.strip().splitlines()[-5:])
    if status == STATUS_PASS:
        return status, f"exit={returncode}"
    detail = _detail_for(status, returncode, output, timeout_label)
    return status, detail + (f"\n{tail}" if tail else "")


def run_python_test(test: Path) -> tuple[str, str]:
    cmd = [sys.executable, str(test)]
    timeout = python_timeout_for(test)
    timeout_label = ""
    try:
        proc = subprocess.run(
            cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
        returncode, output = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        returncode, output = 1, ""
        timeout_label = f"TIMEOUT after {timeout}s"
    status = classify(returncode, output, timeout_label)
    if status == STATUS_PASS:
        return status, f"exit={returncode}"
    tail = "\n".join(output.strip().splitlines()[-8:])
    detail = _detail_for(status, returncode, output, timeout_label)
    return status, detail + (f"\n{tail}" if tail else "")


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
    incomplete: list[str] = []
    unavailable: list[str] = []
    completed = 0
    passed = 0

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
            status, detail = runner(test)  # type: ignore[operator]
            if status == STATUS_PASS:
                passed += 1
            print(f"[{completed}/{total}] {status} {rel}"
                  + (f"  ({detail})" if status != STATUS_PASS else ""))
            if status == STATUS_FAIL:
                failures.append(rel)
            elif status == STATUS_INCOMPLETE:
                incomplete.append(rel)
            if status != STATUS_PASS and args.stop_on_fail:
                stop = True
                break
        if stop:
            break

    not_executed = total - completed
    print(
        "[run_tests] completed={completed}/{total} "
        "passed={passed} failed={fail} incomplete={incomplete} "
        "unavailable={unavail} not_executed={missing}".format(
            completed=completed, total=total, passed=passed,
            fail=len(failures), incomplete=len(incomplete),
            unavail=len(unavailable), missing=not_executed))
    if unavailable:
        print("[run_tests] unavailable tests (not executed):")
        for rel in unavailable:
            print(f"  - {rel} (Godot unavailable)")
    if incomplete:
        print("[run_tests] INCOMPLETE tests (timeout / killed / no verdict):")
        for rel in incomplete:
            print(f"  - {rel}")
        if stop:
            print("[run_tests] remaining tests were not executed (--stop-on-fail)")
    if failures:
        print("[run_tests] failed tests:")
        for failure in failures:
            print(f"  - {failure}")
    if failures or incomplete or unavailable or not_executed:
        return 1
    print("[run_tests] ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
