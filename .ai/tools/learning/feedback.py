#!/usr/bin/env python3
"""Knowledge Feedback Pipeline（Phase 1.66）。

把真实执行结果写回 Phase 1.65 的 Knowledge Store（**同一个库**，不新建平行存储）：

    scenario_results.json + result_analysis.json
        → SCENARIO_OBSERVATION / EXECUTION_OBSERVATION / BEHAVIOR_OBSERVATION
        → TEST_DESIGN_KNOWLEDGE（只在分类为测试设计错误时）
        → PENDING_REVIEW（绝不自动 APPROVED）

门禁（由 knowledge_v2 强制）：

- 场景/执行/行为观察必须有真实 `run_id` 与 Evidence 引用；
- `EXECUTION_OBSERVATION` 还必须有 Attestation 引用；
- 证据文件缺失/digest 不符 → 拒绝入库；
- 推理（INFERENCE）不能 VERIFIED；冲突保留、旧记录不覆盖。

`--review` 是一个**显式**的本地审核步骤（reviewer + reason 写进记录），
用于让第二轮 Planner 消费这些知识；它不是自动批准：命令行必须主动传 `--review`。

用法：
    python .ai/tools/learning/feedback.py --all
    python .ai/tools/learning/feedback.py --all --review
退出码：0 完成；1 有知识被拒绝（原因见输出）；2 输入缺失。
"""

from __future__ import annotations

import argparse
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
import knowledge_v2 as kv                       # noqa: E402

ANALYSIS_PATH = os.path.join(paths.LEARNING_STATE, "result_analysis.json")
SCENARIO_RESULTS = os.path.join(paths.LEARNING_STATE, "scenario_results.json")
SCENARIO_DIR = os.path.join(paths.LEARNING_STATE, "scenarios")
OUT_PATH = os.path.join(paths.LEARNING_STATE, "feedback.json")
REVIEWER = "phase_1_66_local_review"
REVIEW_REASON = "p166: real execution + verified evidence + attestation passed local review"


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


def _digest_file(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return ""


def _scenario(scenario_id: str) -> dict:
    return _load(os.path.join(SCENARIO_DIR, "%s.json" % scenario_id), {})


def _refs(result: dict) -> list[dict]:
    references = []
    bundle = str(result.get("bundle_path") or "")
    if bundle and os.path.isfile(os.path.join(paths.ROOT, bundle)):
        references.append({"kind": "EVIDENCE_REFERENCE", "reference": bundle,
                           "digest": _digest_file(os.path.join(paths.ROOT, bundle))})
    attestation = ".ai/tmp/p166/runs/%s/attestation.json" % result.get("run_id")
    if os.path.isfile(os.path.join(paths.ROOT, attestation)):
        references.append({"kind": "ATTESTATION_REFERENCE", "reference": attestation,
                           "digest": _digest_file(os.path.join(paths.ROOT, attestation))})
    return [reference for reference in references if reference.get("digest")]


def _make(*, scenario: dict, analysis: dict, result: dict, knowledge_type: str, key: str,
          content: dict, confidence: str, references: list[dict]) -> dict:
    return kv.make_record(
        feature_id=scenario["feature_id"], behavior_id=scenario["behavior_id"],
        knowledge_type=knowledge_type, key=key, content=content,
        source_references=references, contract_version=scenario["contract_version"],
        confidence=confidence, run_id=str(result.get("run_id") or ""),
        reason="phase 1.66 feedback from scenario %s (%s)"
               % (scenario.get("scenario_id"), analysis.get("classification")))


def build_candidates() -> dict:
    results = {item["scenario_id"]: item for item in
               (_load(SCENARIO_RESULTS, {}).get("results") or [])}
    analyses = _load(ANALYSIS_PATH, {}).get("analyses") or []
    if not analyses:
        return {"error": "no result analysis", "candidates": []}
    candidates = []
    for analysis in analyses:
        scenario = _scenario(analysis["scenario_id"])
        result = results.get(analysis["scenario_id"]) or {}
        if not scenario or not result:
            continue
        references = _refs(result)
        # 声称“已执行”的观察必须有真实 Evidence 工件；只有 Attestation 不够
        # （否则一次没有原始产物的 Run 也能变成场景/行为知识）。
        claims_execution = result.get("execution_status") not in (None, "", "NOT_EXECUTED")
        has_evidence = any(ref["kind"] == "EVIDENCE_REFERENCE" for ref in references)
        if not references or (claims_execution and not has_evidence):
            candidates.append({"knowledge_type": "SCENARIO_OBSERVATION",
                               "scenario_id": analysis["scenario_id"],
                               "status": "REJECTED",
                               "reason": "no evidence reference" if not claims_execution
                                         else "execution claimed without evidence artifact"})
            continue
        confidence = ("VERIFIED" if (result.get("evidence_status") == "EVIDENCE_VERIFIED"
                                    and result.get("attestation_status") == "ATTESTED_VERIFIED"
                                    and result.get("evaluation_status") == "VERIFIED_PASS")
                      else "HIGH")
        scenario_record = _make(
            scenario=scenario, analysis=analysis, result=result,
            knowledge_type="SCENARIO_OBSERVATION",
            key="scenario:%s" % scenario["scenario_id"],
            # run_id 是记录顶层字段，不重复放进 content：同一场景重跑同样结论时
            # 内容保持一致（幂等），不会因为新 Run ID 产生假冲突。
            content={"scenario_id": scenario["scenario_id"],
                     "scenario_type": scenario["scenario_type"], "rule_id": scenario["rule_id"],
                     "actions": [action.get("type") for action in scenario.get("actions") or []],
                     "expected_observations": scenario.get("expected_observations"),
                     "execution_status": result.get("execution_status"),
                     "evaluation_status": result.get("evaluation_status"),
                     "classification": analysis["classification"]},
            confidence=confidence, references=references)
        execution_record = _make(
            scenario=scenario, analysis=analysis, result=result,
            knowledge_type="EXECUTION_OBSERVATION",
            key="execution:%s" % result.get("run_id"),
            content={"run_id": result.get("run_id"),
                     "execution_status": result.get("execution_status"),
                     "evidence_status": result.get("evidence_status"),
                     "attestation_status": result.get("attestation_status"),
                     "manifest_digest": result.get("manifest_digest"),
                     "scenario_evidence_status": result.get("scenario_evidence_status"),
                     "official_contract_status": result.get("official_contract_status"),
                     "evaluation_status": result.get("evaluation_status"),
                     "trust_level": _load(SCENARIO_RESULTS, {}).get("trust_level")},
            confidence=confidence, references=references)
        candidates.append(scenario_record)
        candidates.append(execution_record)
        if analysis["classification"] in ("CONTRACT_CONFIRMED", "SOURCE_CONFIRMED",
                                          "BEHAVIOR_CONFIRMED"):
            candidates.append(_make(
                scenario=scenario, analysis=analysis, result=result,
                knowledge_type="BEHAVIOR_OBSERVATION",
                key="behavior:%s" % scenario["scenario_id"],
                content={"classification": analysis["classification"],
                         "scenario_type": scenario["scenario_type"],
                         "confirmed_expectation": scenario.get("expected_observations"),
                         "note": "真实观测满足已通过 Scenario Validator 的期望"},
                confidence=confidence, references=references))
        if analysis["classification"] == "TEST_DESIGN_ERROR":
            candidates.append(_make(
                scenario=scenario, analysis=analysis, result=result,
                knowledge_type="TEST_DESIGN_KNOWLEDGE",
                key="test_design:%s" % scenario["scenario_id"],
                content={"classification": analysis["classification"],
                         "reasons": analysis.get("reasons"),
                         "scenario_type": scenario["scenario_type"]},
                confidence="HIGH", references=references))
    return {"error": "", "candidates": candidates}


def write_candidates(review: bool = False) -> dict:
    built = build_candidates()
    if built.get("error"):
        return {"error": built["error"], "written": [], "reviewed": [], "rejected": []}
    written, rejected, reviewed = [], [], []
    for candidate in built["candidates"]:
        if candidate.get("status") == "REJECTED":
            rejected.append(candidate)
            continue
        try:
            record = kv.add_candidate(candidate)
        except kv.KnowledgeError as error:
            rejected.append({"knowledge_id": candidate.get("knowledge_id", ""),
                             "knowledge_type": candidate["knowledge_type"],
                             "status": "REJECTED", "reason": str(error)})
            continue
        references_changed = (candidate.get("source_references") and
                              candidate["source_references"] != record["source_references"])
        if record["verification_status"] in ("ARCHIVED", "SUPERSEDED") or references_changed:
            # 同内容记录曾被归档：不能把归档记录当成「本次写入」，
            # 重新放回候选区（保留 ARCHIVE→REOPEN 历史），仍不自动批准。
            try:
                record = kv.revive(record["knowledge_id"], reviewer=REVIEWER,
                                   reason="re-observed by phase 1.66 feedback (P4)",
                                   source_references=candidate["source_references"],
                                   run_id=str(candidate.get("run_id") or ""))
            except kv.KnowledgeError as error:
                rejected.append({"knowledge_id": record["knowledge_id"],
                                 "status": "REJECTED", "reason": str(error)})
                continue
        written.append(record["knowledge_id"])
        if review and record["verification_status"] == "PENDING_REVIEW":
            try:
                record = kv.approve(record["knowledge_id"], reviewer=REVIEWER,
                                    reason=REVIEW_REASON)
                reviewed.append(record["knowledge_id"])
            except kv.KnowledgeError as error:
                rejected.append({"knowledge_id": record["knowledge_id"],
                                 "status": "REVIEW_BLOCKED", "reason": str(error)})
    document = {"schema": "scenario_knowledge_feedback", "schema_version": 1,
                "generated_at": _now(), "review": bool(review), "reviewer": REVIEWER,
                "written": sorted(set(written)), "reviewed": sorted(set(reviewed)),
                "rejected": rejected,
                "summary": {"candidates": len(built["candidates"]),
                            "written": len(set(written)), "reviewed": len(set(reviewed)),
                            "rejected": len(rejected)}}
    _dump(OUT_PATH, document)
    return document


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--review", action="store_true",
                        help="显式本地审核：approve 本次写入的候选（reviewer 记录在案）")
    args = parser.parse_args(argv)
    document = write_candidates(review=args.review)
    if document.get("error"):
        print(document["error"], file=sys.stderr)
        return 2
    print(json.dumps(document["summary"], ensure_ascii=False))
    for item in document["rejected"][:5]:
        print("REJECTED %s %s" % (item.get("knowledge_type"), item.get("reason")))
    for knowledge_id in document["written"]:
        print("WRITE %s" % knowledge_id)
    return 0 if not document["rejected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
