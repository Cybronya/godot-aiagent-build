#!/usr/bin/env python3
"""Phase 1.66：Result Analyzer 分类测试（不启动 Godot）。

覆盖 9 类结论与「不得误判」规则：
- 证据/Attestation 缺失 → INCONCLUSIVE
- 动作未执行 / 前置失败 → TEST_DESIGN_ERROR（不是 BEHAVIOR_VIOLATION）
- 场景与契约逐字一致 → CONTRACT_CONFIRMED
- 采集侧 FAIL 与场景重算 PASS 冲突 → INCONCLUSIVE
"""

from __future__ import annotations

import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LEARNING = os.path.dirname(HERE)
TOOLS = os.path.dirname(LEARNING)
sys.path[:0] = [LEARNING, os.path.join(TOOLS, "scene_composer")]

import result_analysis as analysis  # noqa: E402
import scenario_generator as gen  # noqa: E402

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


def base_result(**overrides) -> dict:
    payload = {
        "scenario_id": "s-x", "behavior": "openable_door/open", "run_id": "r-1",
        "execution_status": "PASSED", "evidence_status": "EVIDENCE_VERIFIED",
        "attestation_status": "ATTESTED_VERIFIED",
        "scenario_evidence_status": "PASS", "official_contract_status": "PASS",
        "evaluation_status": "VERIFIED_PASS", "bundle_path": "b.json",
        "evidence_digest": "a" * 64, "manifest_digest": "b" * 64,
        "knowledge_refs": ["k-1"], "detail": "",
        "report": {"runs": [{"action_executed": True, "checks": [], "preconditions": []}]},
    }
    payload.update(overrides)
    return payload


def main() -> int:
    door = gen.build(["openable_door/open"])["scenarios"][0]
    trigger = gen.build(["trigger_switch/latch_once"])["scenarios"][0]

    ok("A1: matching contract expectations -> CONTRACT_CONFIRMED",
       analysis.classify(base_result(), door)["classification"] == "CONTRACT_CONFIRMED")
    ok("A2: guard-derived expectation -> SOURCE_CONFIRMED",
       analysis.classify(base_result(), trigger)["classification"] == "SOURCE_CONFIRMED")
    ok("A3: no attestation -> INCONCLUSIVE",
       analysis.classify(base_result(attestation_status="NOT_ATTESTED"), trigger)
       ["classification"] == "INCONCLUSIVE")
    ok("A4: no evidence -> INCONCLUSIVE",
       analysis.classify(base_result(evidence_status="EVIDENCE_ERROR"), trigger)
       ["classification"] == "INCONCLUSIVE")
    ok("A5: environment blocked -> ENVIRONMENT_BLOCKED",
       analysis.classify(base_result(execution_status="ENVIRONMENT_BLOCKED",
                                     scenario_evidence_status="NOT_VERIFIED",
                                     evaluation_status="NOT_EVALUATED"), trigger)
       ["classification"] == "ENVIRONMENT_BLOCKED")
    ok("A6: timeout -> RUNNER_ERROR",
       analysis.classify(base_result(execution_status="TIMEOUT",
                                     scenario_evidence_status="NOT_VERIFIED",
                                     evaluation_status="NOT_EVALUATED"), trigger)
       ["classification"] == "RUNNER_ERROR")
    ok("A7: missing scene -> RESOURCE_ERROR",
       analysis.classify(base_result(execution_status="RUNNER_ERROR",
                                     detail="scene not found",
                                     scenario_evidence_status="NOT_VERIFIED",
                                     evaluation_status="NOT_EVALUATED"), trigger)
       ["classification"] == "RESOURCE_ERROR")
    ok("A8: execution FAILED but scenario recomputed PASS -> INCONCLUSIVE",
       analysis.classify(base_result(execution_status="FAILED"), trigger)
       ["classification"] == "INCONCLUSIVE")

    design = base_result(
        execution_status="FAILED", scenario_evidence_status="FAIL",
        evaluation_status="VERIFIED_FAIL",
        report={"runs": [{"action_executed": False, "checks": [], "preconditions": []}]})
    ok("A9: action never executed -> TEST_DESIGN_ERROR",
       analysis.classify(design, trigger)["classification"] == "TEST_DESIGN_ERROR")

    precondition = base_result(
        execution_status="FAILED", scenario_evidence_status="FAIL",
        evaluation_status="VERIFIED_FAIL",
        report={"runs": [{"action_executed": True, "checks": [],
                          "preconditions": [{"check": "health.current", "status": "MISMATCH",
                                            "observed": 3}]}]})
    ok("A10: unmet precondition -> TEST_DESIGN_ERROR",
       analysis.classify(precondition, trigger)["classification"] == "TEST_DESIGN_ERROR")

    violation = base_result(
        execution_status="FAILED", scenario_evidence_status="FAIL",
        evaluation_status="VERIFIED_FAIL",
        report={"runs": [{"action_executed": True, "preconditions": [],
                          "checks": [{"check": "signal", "status": "SIGNAL_MISMATCH",
                                      "expected": 1, "observed": 2}]}]})
    ok("A11: verified evidence + failing check -> BEHAVIOR_VIOLATION",
       analysis.classify(violation, trigger)["classification"] == "BEHAVIOR_VIOLATION")

    no_check = copy.deepcopy(violation)
    no_check["report"] = {"runs": [{"action_executed": True, "preconditions": [], "checks": []}]}
    ok("A12: FAIL without failing check -> INCONCLUSIVE",
       analysis.classify(no_check, trigger)["classification"] == "INCONCLUSIVE")

    pending = base_result(execution_status="INCONCLUSIVE", scenario_evidence_status="NOT_VERIFIED",
                          evaluation_status="NOT_EVALUATED")
    ok("A13: non-conclusive execution -> INCONCLUSIVE",
       analysis.classify(pending, trigger)["classification"] == "INCONCLUSIVE")
    ok("A14: every classification is in the documented set",
       all(analysis.classify(case, trigger)["classification"] in analysis.CLASSIFICATIONS
           for case in (base_result(), design, pending)))
    print("\n===== test_result_analysis: %d checks, %d failures =====" % (checks, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
