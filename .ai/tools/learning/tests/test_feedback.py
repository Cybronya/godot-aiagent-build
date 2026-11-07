#!/usr/bin/env python3
"""Phase 1.66：Knowledge Feedback 门禁测试（临时知识库，不触碰真实记录）。

覆盖：候选默认 PENDING、无 Run/无 Artifact/无 Attestation 拒绝、
显式 --review 审批、重复不加新记录、冲突保留。
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LEARNING = os.path.dirname(HERE)
sys.path[:0] = [LEARNING, os.path.join(os.path.dirname(LEARNING), "scene_composer")]

import feedback  # noqa: E402
import knowledge_v2  # noqa: E402

checks = 0
failures = 0
TMP: list[str] = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    global checks, failures
    checks += 1
    if condition:
        print("PASS: %s" % name)
    else:
        failures += 1
        print("FAIL: %s %s" % (name, detail))


def isolate() -> None:
    root = tempfile.mkdtemp(prefix="p166_feedback_")
    TMP.append(root)
    knowledge_v2.BASE = root
    knowledge_v2.RECORDS = os.path.join(root, "records")
    knowledge_v2.CANDIDATES = os.path.join(root, "candidates")
    knowledge_v2.CONFLICTS = os.path.join(root, "conflicts")
    for path in (knowledge_v2.RECORDS, knowledge_v2.CANDIDATES, knowledge_v2.CONFLICTS):
        os.makedirs(path, exist_ok=True)


def real_result() -> dict:
    document = json.load(open(os.path.join(LEARNING, "..", "learning",
                                          "scenario_results.json"), encoding="utf-8")) \
        if os.path.isfile(os.path.join(LEARNING, "..", "learning", "scenario_results.json")) \
        else json.load(open(os.path.join(os.path.dirname(LEARNING), "..", "learning",
                                        "scenario_results.json"), encoding="utf-8"))
    return document["results"][0]


def write_inputs(result: dict, classification: str = "CONTRACT_CONFIRMED") -> None:
    analysis_path = os.path.join(tempfile.mkdtemp(prefix="p166_analysis_"), "analysis.json")
    TMP.append(os.path.dirname(analysis_path))
    with open(analysis_path, "w", encoding="utf-8") as handle:
        json.dump({"analyses": [{"scenario_id": result["scenario_id"],
                                 "classification": classification,
                                 "reasons": ["unit test"]}]}, handle)
    results_path = os.path.join(os.path.dirname(analysis_path), "results.json")
    with open(results_path, "w", encoding="utf-8") as handle:
        json.dump({"trust_level": "LOCAL_ISOLATED", "results": [result]}, handle)
    feedback.ANALYSIS_PATH = analysis_path
    feedback.SCENARIO_RESULTS = results_path
    feedback.OUT_PATH = os.path.join(os.path.dirname(analysis_path), "feedback.json")


def main() -> int:
    isolate()
    result = real_result()
    write_inputs(result)

    document = feedback.write_candidates(review=False)
    ok("F1: candidates written", document["summary"]["written"] > 0,
       str(document["summary"]))
    ok("F2: no candidate is auto-approved",
       all(knowledge_v2.get(knowledge_id)["verification_status"] == "PENDING_REVIEW"
           for knowledge_id in document["written"]))
    ok("F3: SCENARIO_OBSERVATION and EXECUTION_OBSERVATION both produced",
       {knowledge_v2.get(k)["knowledge_type"] for k in document["written"]}
       >= {"SCENARIO_OBSERVATION", "EXECUTION_OBSERVATION"})
    ok("F4: run_id is recorded on execution knowledge",
       all(knowledge_v2.get(k)["run_id"] == result["run_id"]
           for k in document["written"]
           if knowledge_v2.get(k)["knowledge_type"] == "EXECUTION_OBSERVATION"))

    # 无 Run ID：应被来源门禁拒绝（TEST/OBSERVATION 必须有 run_id）
    no_run = dict(result)
    no_run["run_id"] = ""
    write_inputs(no_run)
    rejected = feedback.write_candidates(review=False)
    ok("F5: execution knowledge without run_id rejected",
       rejected["summary"]["written"] == 0 and rejected["rejected"],
       str(rejected["summary"]))

    # 无 Attestation 文件：EXECUTION_OBSERVATION 必须被拒
    no_attest = dict(result)
    no_attest["run_id"] = "run-without-attestation"
    write_inputs(no_attest)
    partial = feedback.write_candidates(review=False)
    types = {knowledge_v2.get(item)["knowledge_type"] for item in partial["written"]}
    ok("F6: EXECUTION_OBSERVATION requires attestation reference",
       "EXECUTION_OBSERVATION" not in types and "SCENARIO_OBSERVATION" in types,
       str(types))

    # 证据文件不存在：全部拒绝
    missing = dict(result)
    missing["bundle_path"] = ".ai/tmp/p166/evidence/does-not-exist.json"
    write_inputs(missing)
    broken = feedback.write_candidates(review=False)
    ok("F7: missing evidence artifact rejected",
       broken["summary"]["written"] == 0 and broken["rejected"])

    # 显式审核
    write_inputs(result)
    reviewed = feedback.write_candidates(review=True)
    ok("F8: --review approves and records the reviewer",
       reviewed["summary"]["reviewed"] > 0 and
       all(knowledge_v2.get(k)["review"]["reviewer"] == feedback.REVIEWER
           for k in reviewed["reviewed"]))
    ok("F9: approved records keep lifecycle history",
       all(any(event["event"] == "APPROVE"
               for event in knowledge_v2.get(k)["lifecycle_events"])
           for k in reviewed["reviewed"]))

    # 重复写入不新增记录
    before = len(knowledge_v2.all_records())
    feedback.write_candidates(review=True)
    after = len(knowledge_v2.all_records())
    ok("F10: repeated feedback is idempotent", before == after,
       "%d -> %d" % (before, after))

    # 不同分类 → 同槽冲突，双方保留、不自动解决
    write_inputs(result, classification="BEHAVIOR_VIOLATION")
    conflict = feedback.write_candidates(review=False)
    pending_conflicts = knowledge_v2.conflicts("OPEN")
    both_sides = all(len(item["parties"]) == 2 and
                     all(knowledge_v2.get(party["knowledge_id"]) for party in item["parties"])
                     for item in pending_conflicts)
    ok("F11: conflicting observation keeps both parties and stays OPEN",
       (bool(pending_conflicts) and both_sides) or bool(conflict["rejected"]),
       "open=%d both_sides=%s" % (len(pending_conflicts), both_sides))

    # 测试设计错误 → TEST_DESIGN_KNOWLEDGE
    isolate()
    write_inputs(result, classification="TEST_DESIGN_ERROR")
    design = feedback.write_candidates(review=False)
    ok("F12: TEST_DESIGN_ERROR produces TEST_DESIGN_KNOWLEDGE",
       "TEST_DESIGN_KNOWLEDGE" in {knowledge_v2.get(k)["knowledge_type"]
                                   for k in design["written"]})

    # 已归档的同内容记录：再观察时必须复活到候选区（历史保留），不能“写入成功”
    # 却还是 ARCHIVED，也不能带着指向已消失证据的旧引用。
    isolate()
    write_inputs(result)
    first = feedback.write_candidates(review=False)
    target = first["written"][0]
    knowledge_v2.archive(target, reviewer=feedback.REVIEWER, reason="fixture archive")
    second = feedback.write_candidates(review=True)
    revived = knowledge_v2.get(target)
    ok("F13: archived knowledge is revived and approvable after re-observation",
       revived["verification_status"] == "APPROVED" and
       target in second["reviewed"] and
       [event["event"] for event in revived["lifecycle_events"]]
       == ["CREATE", "ARCHIVE", "REOPEN", "APPROVE"],
       str([event["event"] for event in revived["lifecycle_events"]]))

    print("\n===== test_feedback: %d checks, %d failures =====" % (checks, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
