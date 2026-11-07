#!/usr/bin/env python3
"""Test Result Analyzer（Phase 1.66）。

把真实执行结果解释成**可追溯的学习结论**，并明确区分：

    CONTRACT_CONFIRMED   场景期望与契约一致，且真实观测满足
    SOURCE_CONFIRMED     场景期望来自源码事实，且真实观测满足
    BEHAVIOR_CONFIRMED   场景期望不来自契约/源码直接事实，但观测满足且证据完整
    BEHAVIOR_VIOLATION   证据完整、场景合法，但真实观测违反期望
    TEST_DESIGN_ERROR    动作未执行/前置不成立/期望不可验证
    ENVIRONMENT_BLOCKED  Godot/资源不可用
    RUNNER_ERROR         探针/采集器故障、超时
    RESOURCE_ERROR       场景/夹具缺失
    INCONCLUSIVE         证据/Attestation/评估不完整，无法下结论

铁律：没有真实 Run + 验证过的证据 + Attestation，就不给 BEHAVIOR_VIOLATION/CONFIRMED；
无法确定一律 INCONCLUSIVE，不为了显得聪明而编根因。

用法：
    python .ai/tools/learning/result_analysis.py --all
退出码：0 分析完成；2 输入缺失。
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.dirname(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths                                    # noqa: E402
import scenario_generator                       # noqa: E402

RESULTS_DIR = os.path.join(paths.LEARNING_STATE, "results")
INDEX_PATH = os.path.join(paths.LEARNING_STATE, "result_analysis.json")
SCENARIO_RESULTS = os.path.join(paths.LEARNING_STATE, "scenario_results.json")

CLASSIFICATIONS = ("CONTRACT_CONFIRMED", "SOURCE_CONFIRMED", "BEHAVIOR_CONFIRMED",
                   "BEHAVIOR_VIOLATION", "TEST_DESIGN_ERROR", "ENVIRONMENT_BLOCKED",
                   "RUNNER_ERROR", "RESOURCE_ERROR", "INCONCLUSIVE")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load(path: str, default):
    if not os.path.isfile(path):
        return default
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _dump(path: str, document) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _digest(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _scenario(scenario_id: str) -> dict:
    path = os.path.join(scenario_generator.SCENARIO_DIR, "%s.json" % scenario_id)
    return _load(path, {})


def _derivation_is_contract(scenario: dict) -> bool:
    """场景期望是否与 Feature 契约逐字一致（用于区分 CONTRACT_CONFIRMED）。"""
    record = _load(os.path.join(paths.LEARNING_STATE, "scenarios.json"), {})
    base = next((item for item in record.get("scenarios") or []
                 if item["scenario_id"] == scenario["scenario_id"]), None)
    if base is None:
        return False
    try:
        import feature_behavior_evidence as fbe       # noqa: PLC0415
        contracts, _reports = fbe.build_contracts(scenario["feature_id"], "Features")
    except Exception:                                  # noqa: BLE001 - 契约不可读即无法确认
        return False
    contract = next((item for item in contracts
                     if str(item["behavior"]) == scenario["behavior_id"]), None)
    if contract is None:
        return False
    canonical = lambda items: _digest([{key: value for key, value in item.items()}
                                       for item in items])   # noqa: E731
    return canonical(contract["expected"]) == canonical(scenario["expected_observations"])


def classify(result: dict, scenario: dict) -> dict:
    classification = "INCONCLUSIVE"
    reasons = []
    execution = result.get("execution_status")
    detail = str(result.get("detail") or "")
    if execution == "ENVIRONMENT_BLOCKED":
        classification = "ENVIRONMENT_BLOCKED"
        reasons.append("execution_status=ENVIRONMENT_BLOCKED")
    elif execution in ("TIMEOUT", "RUNNER_ERROR"):
        classification = ("RESOURCE_ERROR" if ("scene" in detail.lower()
                                               or "fixture" in detail.lower())
                          else "RUNNER_ERROR")
        reasons.append("execution_status=%s" % execution)
    elif execution not in ("PASSED", "FAILED"):
        classification = "INCONCLUSIVE"
        reasons.append("execution_status=%s is not a conclusive run" % execution)
    else:
        evidence_ok = result.get("evidence_status") == "EVIDENCE_VERIFIED"
        attestation_ok = result.get("attestation_status") == "ATTESTED_VERIFIED"
        scenario_status = result.get("scenario_evidence_status")
        evaluation = result.get("evaluation_status")
        reasons.append("evidence=%s attestation=%s scenario_validator=%s evaluation=%s"
                       % (result.get("evidence_status"), result.get("attestation_status"),
                          scenario_status, evaluation))
        if execution == "FAILED" and scenario_status == "PASS":
            # 场景期望重算满足、采集侧却 FAIL：不能互相掩盖
            classification = "INCONCLUSIVE"
            reasons.append("scenario expectation recomputed as met while execution reported FAIL")
        elif not (evidence_ok and attestation_ok):
            classification = "INCONCLUSIVE"
            reasons.append("evidence or attestation not verified; no behavioral conclusion")
        elif execution == "PASSED" and evaluation == "VERIFIED_PASS":
            if _derivation_is_contract(scenario):
                classification = "CONTRACT_CONFIRMED"
            elif scenario.get("rule_id") in ("idempotent_repeat", "foreign_group_ignored",
                                             "invalid_slot_rejected", "post_terminal_input_ignored"):
                classification = "SOURCE_CONFIRMED"
            else:
                classification = "BEHAVIOR_CONFIRMED"
            reasons.append("real observation satisfies %s scenario expectation"
                           % scenario.get("scenario_type"))
        elif execution == "PASSED":
            classification = "INCONCLUSIVE"
            reasons.append("execution passed but scenario evaluation=%s" % evaluation)
        else:
            failure = _failure_kind(result, scenario)
            classification = failure["classification"]
            reasons.extend(failure["reasons"])
    return {"scenario_id": result.get("scenario_id"), "behavior": result.get("behavior"),
            "classification": classification, "reasons": reasons,
            "run_id": result.get("run_id"), "scenario_type": scenario.get("scenario_type"),
            "rule_id": scenario.get("rule_id"),
            "knowledge_refs": result.get("knowledge_refs") or scenario.get("knowledge_refs") or [],
            "evidence": {"bundle": result.get("bundle_path"),
                         "bundle_digest": result.get("evidence_digest"),
                         "manifest_digest": result.get("manifest_digest")},
            "statuses": {key: result.get(key) for key in
                         ("execution_status", "evidence_status", "attestation_status",
                          "scenario_evidence_status", "official_contract_status",
                          "evaluation_status")},
            "analyzed_at": _now()}


def _failure_kind(result: dict, scenario: dict) -> dict:
    """FAILED 的执行：先排查测试设计/环境，最后才可能是行为缺陷。"""
    report = result.get("report") or {}
    runs = report.get("runs") or []
    reasons = ["execution_status=FAILED", "reason=%s" % report.get("reason")]
    if not runs:
        return {"classification": "RUNNER_ERROR",
                "reasons": reasons + ["no per-replay run record"]}
    run = runs[0]
    if not run.get("action_executed"):
        return {"classification": "TEST_DESIGN_ERROR",
                "reasons": reasons + ["the action never executed"]}
    failing = [check for check in run.get("checks") or []
               if str(check.get("status")) != "PASS"]
    muted = [check for check in run.get("preconditions") or []
             if str(check.get("status")) != "PASS"]
    if muted:
        return {"classification": "TEST_DESIGN_ERROR",
                "reasons": reasons + ["precondition %s not met (%s)"
                                      % (muted[0].get("check"), muted[0].get("observed"))]}
    if not failing:
        return {"classification": "INCONCLUSIVE",
                "reasons": reasons + ["no failing check recorded"]}
    if result.get("scenario_evidence_status") != "FAIL":
        return {"classification": "INCONCLUSIVE",
                "reasons": reasons + ["scenario evidence verdict is not FAIL"]}
    return {"classification": "BEHAVIOR_VIOLATION",
            "reasons": reasons + ["%s expected %s observed %s"
                                  % (failing[0].get("check"), failing[0].get("expected"),
                                     failing[0].get("observed"))]}


def analyze_all() -> dict:
    source = _load(SCENARIO_RESULTS, {})
    results = source.get("results") or []
    if not results:
        return {"error": "no scenario results", "analyses": []}
    analyses = []
    for result in results:
        scenario = _scenario(result["scenario_id"])
        item = classify(result, scenario)
        item["label"] = source.get("label", "")
        analyses.append(item)
        _dump(os.path.join(RESULTS_DIR, "%s.json" % item["scenario_id"]), item)
    summary: dict = {}
    for item in analyses:
        summary[item["classification"]] = summary.get(item["classification"], 0) + 1
    document = {"schema": "scenario_result_analysis", "schema_version": 1,
                "generated_at": _now(), "source": "scenario_results.json",
                "summary": summary, "analyses": analyses}
    _dump(INDEX_PATH, document)
    return document


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)
    document = analyze_all()
    if document.get("error"):
        print(document["error"], file=sys.stderr)
        return 2
    for item in document["analyses"]:
        print("%s %s -> %s" % (item["scenario_id"], item["behavior"], item["classification"]))
    print(json.dumps(document["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
