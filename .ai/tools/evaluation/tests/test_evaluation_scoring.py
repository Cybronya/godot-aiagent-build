#!/usr/bin/env python3
"""Evaluation Scoring 自测（Phase 1.36）。

覆盖判定口径本身 —— 评估报告里每个数字都由这些函数折叠而来，所以它们必须有测试：
    阶段折叠（FAIL 优先 / SKIP / NOT_EXECUTED / 未知状态）
    任务判定（必需阶段未执行 ≠ 通过）
    尝试判定（只看自己的步骤，不借用其它尝试的证据）
    指标分母（未执行任务不进分母；auto_repair 与 plan_revision 分开统计）

用法：python .ai/tools/evaluation/tests/test_evaluation_scoring.py
全部通过输出 PASS 并退出 0；任一失败输出 FAIL 并退出 1。
"""

from __future__ import annotations

import sys
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
EVAL_DIR = TEST_DIR.parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

import scoring  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_failures: list[str] = []
_checks = 0


def ok(name: str, condition: bool, detail: str = "") -> None:
    global _checks
    _checks += 1
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def step(step_id: str, phase: str, status: str) -> dict:
    return {"id": step_id, "phase": phase, "status": status}


def test_normalize() -> None:
    ok("normalize: pass lower-case", scoring.normalize_status("pass") == "PASS")
    ok("normalize: unknown → INCOMPLETE",
       scoring.normalize_status("whatever") == "INCOMPLETE")
    ok("normalize: empty → INCOMPLETE", scoring.normalize_status("") == "INCOMPLETE")


def test_fold() -> None:
    ok("fold: empty → NOT_EXECUTED",
       scoring.fold_statuses([]) == "NOT_EXECUTED")
    ok("fold: FAIL wins over PASS",
       scoring.fold_statuses(["PASS", "FAIL", "PASS"]) == "FAIL")
    ok("fold: INCOMPLETE beats SKIP",
       scoring.fold_statuses(["SKIP", "INCOMPLETE"]) == "INCOMPLETE")
    ok("fold: all SKIP stays SKIP",
       scoring.fold_statuses(["SKIP", "SKIP"]) == "SKIP")


def test_phase_status() -> None:
    info = scoring.phase_status([step("a", "behavior", "PASS"),
                                 step("b", "behavior", "FAIL")])
    ok("phase: any FAIL → FAIL", info["status"] == "FAIL", str(info))
    ok("phase: checks counts evidence", info["checks"] == 2, str(info))
    ok("phase: failed steps named", "b" in info["detail"], str(info))
    missing = scoring.phase_status([])
    ok("phase: no evidence → NOT_EXECUTED", missing["status"] == "NOT_EXECUTED")


def test_task_verdict() -> None:
    phases = {phase: {"status": "PASS", "checks": 1} for phase in scoring.PHASES}
    ok("verdict: all PASS → PASS",
       scoring.task_verdict(phases)["status"] == "PASS")
    phases_missing = dict(phases)
    phases_missing["behavior"] = {"status": "NOT_EXECUTED", "checks": 0}
    verdict = scoring.task_verdict(phases_missing)
    ok("verdict: NOT_EXECUTED is not PASS", verdict["status"] == "INCOMPLETE",
       str(verdict))
    phases_fail = dict(phases)
    phases_fail["behavior"] = {"status": "FAIL", "checks": 1}
    ok("verdict: FAIL → FAIL",
       scoring.task_verdict(phases_fail)["status"] == "FAIL")
    subset = {"plan": {"status": "PASS", "checks": 1},
              "behavior": {"status": "PASS", "checks": 1}}
    ok("verdict: required subset respected",
       scoring.task_verdict(subset, ["plan", "behavior"])["status"] == "PASS")
    ok("verdict: absent required phase blocks",
       scoring.task_verdict({"plan": {"status": "PASS", "checks": 1}},
                            ["plan", "behavior"])["status"] == "INCOMPLETE")


def test_attempt_passed() -> None:
    ok("attempt: own steps all PASS → True",
       scoring.attempt_passed([step("a", "plan", "PASS")]))
    ok("attempt: one FAIL → False",
       not scoring.attempt_passed([step("a", "plan", "PASS"),
                                   step("b", "artifacts", "FAIL")]))
    ok("attempt: empty → False", not scoring.attempt_passed([]))


def test_metrics() -> None:
    runs = [
        {"task_id": "T1", "verdict": "PASS", "first_pass": True,
         "attempts": [{"kind": "initial", "passed": True}],
         "phases": {"regression": {"status": "PASS", "checks": 2}},
         "duration_s": 10.0},
        {"task_id": "T2", "verdict": "PASS", "first_pass": False,
         "attempts": [{"kind": "initial", "passed": False},
                      {"kind": "plan_revision", "passed": True}],
         "phases": {"regression": {"status": "PASS", "checks": 1}},
         "duration_s": 5.0},
        {"task_id": "T3", "verdict": "FAIL", "first_pass": False,
         "attempts": [{"kind": "framework", "passed": False}],
         "phases": {"regression": {"status": "FAIL", "checks": 1}},
         "duration_s": 1.0},
        {"task_id": "T4", "verdict": "NOT_EXECUTED", "first_pass": False,
         "attempts": [], "phases": {}, "duration_s": 0.0},
    ]
    metrics = scoring.compute_metrics(runs)
    ok("metrics: attempted excludes NOT_EXECUTED",
       metrics["tasks_attempted"] == 3, str(metrics["tasks_attempted"]))
    ok("metrics: first_pass denominator = attempted",
       metrics["first_pass_rate"]["denominator"] == 3
       and metrics["first_pass_rate"]["numerator"] == 1,
       str(metrics["first_pass_rate"]))
    ok("metrics: final_pass 2/3",
       metrics["final_pass_rate"]["numerator"] == 2
       and metrics["final_pass_rate"]["denominator"] == 3,
       str(metrics["final_pass_rate"]))
    ok("metrics: framework repair counted separately 0/1",
       metrics["auto_repair_success_rate"]["numerator"] == 0
       and metrics["auto_repair_success_rate"]["denominator"] == 1,
       str(metrics["auto_repair_success_rate"]))
    ok("metrics: plan revision 1/1",
       metrics["plan_revision_success_rate"]["numerator"] == 1
       and metrics["plan_revision_success_rate"]["denominator"] == 1,
       str(metrics["plan_revision_success_rate"]))
    # 分母 = 实际执行的回归检查数：T1 2 项 + T2 1 项 + T3 1 项 = 4（T4 未执行不计入）
    ok("metrics: regression defects 1/4",
       metrics["regression_defects"]["value"] == 1
       and metrics["regression_defects"]["denominator"] == 4,
       str(metrics["regression_defects"]))
    ok("metrics: duration per task recorded",
       metrics["task_duration_s"].get("T1") == 10.0
       and metrics["total_duration_s"] == 16.0,
       str(metrics["task_duration_s"]))
    ok("metrics: zero denominator is null, not 0",
       scoring.compute_metrics([])["first_pass_rate"]["value"] is None)
    ok("metrics: cost defaults to UNAVAILABLE",
       metrics["cost"]["status"] == "UNAVAILABLE", str(metrics["cost"]))


def main() -> int:
    test_normalize()
    test_fold()
    test_phase_status()
    test_task_verdict()
    test_attempt_passed()
    test_metrics()
    if _failures:
        print("FAIL: %d evaluation scoring check(s) failed" % len(_failures))
        return 1
    print("PASS: evaluation scoring (%d checks)" % _checks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
