#!/usr/bin/env python3
"""Phase 1.68.2：官方契约执行入口的非 Godot 测试。"""

from __future__ import annotations

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LEARNING = os.path.dirname(HERE)
TOOLS = os.path.dirname(LEARNING)
sys.path[:0] = [LEARNING, os.path.join(TOOLS, "scene_composer"),
                os.path.join(TOOLS, "validator"),
                os.path.join(TOOLS, "validator", "execution")]

import scenario_run as run  # noqa: E402

checks = 0
failures = 0


def ok(name: str, condition: bool, detail: str = "") -> None:
    global checks, failures
    checks += 1
    if condition:
        print("PASS: %s" % name)
    else:
        failures += 1
        print("FAIL: %s %s" % (name, detail))


def main() -> int:
    original = (run.OFFICIAL_ROOT, run.OFFICIAL_EVIDENCE_DIR, run.OFFICIAL_RUNS_DIR,
                run.OFFICIAL_RECORDS_DIR, run.OFFICIAL_RESULTS_INDEX)
    tmp_root = os.path.join(os.path.dirname(TOOLS), "tmp")
    os.makedirs(tmp_root, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=tmp_root) as tmp:
        run.OFFICIAL_ROOT = os.path.join(tmp, "official")
        run.OFFICIAL_EVIDENCE_DIR = os.path.join(run.OFFICIAL_ROOT, "evidence")
        run.OFFICIAL_RUNS_DIR = os.path.join(run.OFFICIAL_ROOT, "runs")
        run.OFFICIAL_RECORDS_DIR = os.path.join(run.OFFICIAL_ROOT, "records")
        run.OFFICIAL_RESULTS_INDEX = os.path.join(run.OFFICIAL_ROOT, "results.json")

        missing = run.run_official_contract("no_such_feature/no_such_behavior")
        ok("O1: missing contract is a visible RUNNER_ERROR",
           missing["execution_status"] == "RUNNER_ERROR")
        ok("O2: missing contract does not claim coverage",
           missing["official_coverage_status"] == "NOT_COVERED" and
           not missing["bundle_path"])
        ok("O3: missing contract is recorded in the official index",
           os.path.isfile(run.OFFICIAL_RESULTS_INDEX))

        plan = run.official_plan("openable_door", "open")
        ok("O4: official plan is separated from scenario execution",
           plan["kind"] == "OFFICIAL_CONTRACT" and plan["behavior"] == "openable_door/open")
        ok("O5: official plan carries contract actions and expected",
           any(item["name"] == "contract_actions" and item["ok"]
               for item in plan["prerequisites"]) and
           any(item["name"] == "contract_expected" and item["ok"]
               for item in plan["prerequisites"]))
        ok("O6: official plan does not carry a scenario id",
           plan.get("scenario_id") is None)

        original_require = run.env_paths.require_godot
        run.env_paths.require_godot = lambda _root: (_ for _ in ()).throw(
            RuntimeError("godot missing"))
        try:
            startup_error = run.run_official_contract("openable_door/open")
        finally:
            run.env_paths.require_godot = original_require
        ok("O6b: Godot startup failure is a visible RUNNER_ERROR",
           startup_error["execution_status"] == "RUNNER_ERROR" and
           not startup_error["bundle_path"] and
           startup_error["official_coverage_status"] == "NOT_COVERED")

    # 执行状态映射：超时/采集失败/成功/不匹配分别可见。
    ok("O7: probe timeout maps to TIMEOUT",
       run._execution_status({"status": "INSUFFICIENT", "reason": "probe_timeout"})[0]
       == "TIMEOUT")
    ok("O8: missing evidence maps to RUNNER_ERROR",
       run._execution_status({"status": "INSUFFICIENT",
                              "reason": "evidence_unavailable", "runs": []})[0]
       == "RUNNER_ERROR")
    ok("O9: mismatch maps to FAILED",
       run._execution_status({"status": "MISMATCH", "reason": "contract_violation"})[0]
       == "FAILED")
    ok("O10: PASS maps to PASSED",
       run._execution_status({"status": "PASS", "reason": "ok"})[0] == "PASSED")

    summary = run._official_summary([
        {"execution_status": "PASSED", "official_evaluation_status": "PASS",
         "attestation_status": "ATTESTED_VERIFIED", "official_coverage_status": "OFFICIAL_PASS"},
        {"execution_status": "PASSED", "official_evaluation_status": "FAIL",
         "attestation_status": "ATTESTED_VERIFIED", "official_coverage_status": "NOT_COVERED"},
        {"execution_status": "RUNNER_ERROR", "official_evaluation_status": "INCOMPLETE",
         "attestation_status": "NOT_ATTESTED", "official_coverage_status": "NOT_COVERED"},
    ])
    ok("O11: official summary counts PASS/FAIL/INCOMPLETE independently",
       summary["passed"] == 1 and summary["failed"] == 1 and
       summary["incomplete"] == 1 and summary["fully_covered"] == 1 and
       summary["attested"] == 2)

    run.OFFICIAL_ROOT, run.OFFICIAL_EVIDENCE_DIR, run.OFFICIAL_RUNS_DIR, \
        run.OFFICIAL_RECORDS_DIR, run.OFFICIAL_RESULTS_INDEX = original

    print("\n===== test_official_contract_run: %d checks, %d failures ====="
          % (checks, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
