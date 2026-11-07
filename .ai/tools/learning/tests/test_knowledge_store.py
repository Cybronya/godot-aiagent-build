#!/usr/bin/env python3
"""Phase 1.65：Typed Knowledge Store 测试（审批 / 冲突 / 版本 / 撤销 / 来源门禁）。

全部在临时目录里跑，不触碰 `.ai/knowledge/**` 的真实记录。
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LEARNING = os.path.dirname(HERE)
sys.path[:0] = [LEARNING]

import knowledge_v2  # noqa: E402
import paths  # noqa: E402

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
    root = tempfile.mkdtemp(prefix="p165_knowledge_")
    TMP.append(root)
    knowledge_v2.BASE = root
    knowledge_v2.RECORDS = os.path.join(root, "records")
    knowledge_v2.CANDIDATES = os.path.join(root, "candidates")
    knowledge_v2.CONFLICTS = os.path.join(root, "conflicts")


def source_record(**overrides) -> dict:
    digest = knowledge_v2._file_digest("Features/openable_door/openable_door.gd")
    payload = dict(
        feature_id="openable_door", behavior_id="open", knowledge_type="SOURCE_OBSERVATION",
        key="entry_points", content={"entry_points": [{"name": "set_open"}]},
        source_references=[{"kind": "SOURCE_REFERENCE",
                            "reference": "Features/openable_door/openable_door.gd:32#func=set_open",
                            "digest": digest}],
        contract_version="0550357495e5", confidence="HIGH")
    payload.update(overrides)
    return knowledge_v2.make_record(**payload)


def approve(record: dict) -> dict:
    knowledge_v2.add_candidate(record)
    return knowledge_v2.approve(record["knowledge_id"], reviewer="tester", reason="unit test")


def main() -> int:
    isolate()

    # K1 自动生成默认待审
    record = source_record()
    stored = knowledge_v2.add_candidate(record)
    ok("K1: generated knowledge starts PENDING_REVIEW",
       stored["verification_status"] == "PENDING_REVIEW")
    ok("K2: knowledge_id is content derived and stable",
       stored["knowledge_id"].startswith("k-") and len(stored["knowledge_id"]) == 18)

    # K3 来源门禁：缺少 SOURCE_REFERENCE
    bad = knowledge_v2.make_record(
        feature_id="openable_door", behavior_id="open", knowledge_type="SOURCE_OBSERVATION",
        key="x", content={"a": 1},
        source_references=[{"kind": "CONTRACT_REFERENCE",
                            "reference": "Features/openable_door/template.yaml#behavior=open"}],
        contract_version="0550357495e5", confidence="HIGH")
    try:
        knowledge_v2.add_candidate(bad)
        ok("K3: SOURCE_OBSERVATION without source reference is rejected", False)
    except knowledge_v2.KnowledgeError as error:
        ok("K3: SOURCE_OBSERVATION without source reference is rejected",
           "requires one of" in str(error))

    # K4 digest 不匹配 → 拒绝（不能拿旧源码分析冒充当前源码）
    stale_digest = source_record(source_references=[{
        "kind": "SOURCE_REFERENCE",
        "reference": "Features/openable_door/openable_door.gd:32#func=set_open",
        "digest": "0" * 64}])
    try:
        knowledge_v2.add_candidate(stale_digest)
        ok("K4: stale implementation digest is rejected", False)
    except knowledge_v2.KnowledgeError as error:
        ok("K4: stale implementation digest is rejected", "digest mismatch" in str(error))

    # K5 引用文件不存在 → 拒绝
    missing = source_record(source_references=[{
        "kind": "SOURCE_REFERENCE", "reference": "Features/nope/nope.gd:1"}],
        content={"entry_points": [{"name": "nope"}]})
    try:
        knowledge_v2.add_candidate(missing)
        ok("K5: missing source file is rejected", False)
    except knowledge_v2.KnowledgeError as error:
        ok("K5: missing source file is rejected", "file missing" in str(error))

    # K6 INVALID mutation 不能当缺陷知识
    invalid = knowledge_v2.make_record(
        feature_id="openable_door", behavior_id="open", knowledge_type="MUTATION_OBSERVATION",
        key="mutation:M99", content={"mutation_id": "M99"},
        source_references=[{"kind": "MUTATION_REFERENCE", "reference": "x.json"}],
        contract_version="0550357495e5", confidence="HIGH", run_id="r",
        mutation_verdict="INVALID_MUTANT")
    try:
        knowledge_v2.add_candidate(invalid)
        ok("K6: INVALID_MUTANT is rejected as mutation knowledge", False)
    except knowledge_v2.KnowledgeError as error:
        ok("K6: INVALID_MUTANT is rejected as mutation knowledge",
           "MUTANT_KILLED" in str(error))

    # K7 审批必须带 reviewer/reason
    try:
        knowledge_v2.approve(record["knowledge_id"], reviewer="", reason="")
        ok("K7: approval requires reviewer and reason", False)
    except knowledge_v2.KnowledgeError:
        ok("K7: approval requires reviewer and reason", True)

    # K8/K9 审批 + 历史保留
    approved = approve(record)
    ok("K8: approved record moves to the authoritative area",
       approved["verification_status"] == "APPROVED" and approved["review"]["reviewer"] == "tester")
    ok("K9: approval keeps a lifecycle event trail",
       [event["event"] for event in approved["lifecycle_events"]] == ["CREATE", "APPROVE"])

    # K10 重复内容不产生新记录
    duplicate = knowledge_v2.add_candidate(source_record())
    ok("K10: identical content returns the existing record (no duplicate)",
       duplicate["knowledge_id"] == approved["knowledge_id"])

    # K11 同槽不同内容 → 冲突，且阻断审批
    changed = source_record(content={"entry_points": [{"name": "set_open_v2"}]})
    conflict_record = knowledge_v2.add_candidate(changed)
    ok("K11: conflicting content creates a conflict and stays pending",
       conflict_record["verification_status"] == "PENDING_REVIEW"
       and conflict_record["conflict_ids"])
    open_conflicts = knowledge_v2.conflicts("OPEN")
    ok("K12: conflict keeps both parties",
       len(open_conflicts) == 1 and len(open_conflicts[0]["parties"]) == 2)
    try:
        knowledge_v2.approve(conflict_record["knowledge_id"], reviewer="tester", reason="x")
        ok("K13: unresolved conflict blocks approval", False)
    except knowledge_v2.KnowledgeError as error:
        ok("K13: unresolved conflict blocks approval", "conflict" in str(error))

    # K14 解决冲突后审批 → 旧记录 SUPERSEDED（不删除）
    knowledge_v2.resolve_conflict(open_conflicts[0]["conflict_id"], resolution="源码已更新",
                                  reviewer="tester")
    superseding = knowledge_v2.approve(conflict_record["knowledge_id"], reviewer="tester",
                                       reason="after source change")
    old = knowledge_v2.get(approved["knowledge_id"])
    ok("K14: new approval supersedes old record without deleting it",
       superseding["verification_status"] == "APPROVED"
       and old["verification_status"] == "SUPERSEDED"
       and old["superseded_by"] == superseding["knowledge_id"])

    # K15 撤销后不能重新审批；记录仍在
    revoked = knowledge_v2.revoke(superseding["knowledge_id"], reviewer="tester",
                                  reason="wrong source")
    ok("K15: revoke keeps the record with REVOKED status",
       revoked["verification_status"] == "REVOKED" and knowledge_v2.get(
           superseding["knowledge_id"])["verification_status"] == "REVOKED")
    try:
        knowledge_v2.approve(superseding["knowledge_id"], reviewer="tester", reason="again")
        ok("K16: revoked knowledge cannot be approved again", False)
    except knowledge_v2.KnowledgeError:
        ok("K16: revoked knowledge cannot be approved again", True)

    # K17 INFERENCE 必须有 derivations，且不能标 VERIFIED
    inference = knowledge_v2.make_record(
        feature_id="openable_door", behavior_id="open", knowledge_type="INFERENCE",
        key="inference:guard", content={"claim": "guard prevents duplicate signal"},
        source_references=[{"kind": "CONTRACT_REFERENCE",
                            "reference": "Features/openable_door/template.yaml#behavior=open"}],
        contract_version="0550357495e5", confidence="MEDIUM")
    try:
        knowledge_v2.add_candidate(inference)
        ok("K17: inference without derivations is rejected", False)
    except knowledge_v2.KnowledgeError as error:
        ok("K17: inference without derivations is rejected", "derivations" in str(error))
    inference_verified = dict(inference, confidence="VERIFIED",
                             derivations=[revoked["knowledge_id"]])
    try:
        knowledge_v2.add_candidate(inference_verified)
        ok("K18: inference cannot claim VERIFIED confidence", False)
    except knowledge_v2.KnowledgeError as error:
        ok("K18: inference cannot claim VERIFIED confidence", "cannot be VERIFIED" in str(error))

    # K19 过期检测
    stale = knowledge_v2.staleness(approved, current_contract_version="deadbeef0000")
    ok("K19: stale contract version is detected", bool(stale))

    # K20 汇总
    summary = knowledge_v2.summary()
    ok("K20: summary counts statuses and conflicts",
       summary["records"] == 2 and summary["by_status"] == {"SUPERSEDED": 1, "REVOKED": 1}
       and summary["conflicts_total"] == 1
       and summary["behaviors_with_knowledge"] == 1,
       str(summary))

    for directory in TMP:
        shutil.rmtree(directory, ignore_errors=True)
    print("\n===== test_knowledge_store: %d checks, %d failures =====" % (checks, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
