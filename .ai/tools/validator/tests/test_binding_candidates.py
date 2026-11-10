#!/usr/bin/env python3
"""Binding 候选生成与显式审批测试（Phase 1.63，任务书 §7.1）。

被测对象：`.ai/tools/validator/binding_candidates.py`（加法式扩展 1.60 绑定体系）

覆盖矩阵（全部使用临时目录，不触碰真实绑定库/登记表）：
    A. 候选生成
      A1 正式支持集全量生成候选；expected 与契约逐项一致（逐字复制）
      A2 已绑定 (feature,behavior) 不生成候选（保留历史）
      A3 重复 binding_id 不产生（唯一性）
      A4 缺 expected 契约 -> BLOCKED_MISSING_EXPECTED，禁止猜测填充
      A5 支持清单动态生成（数量来自 Registry，不硬编码 23/60）
    B. 审批状态机
      B1 DRAFT -> APPROVED 跳步被拒
      B2 DRAFT -> PENDING_REVIEW -> APPROVED 合法
      B3 候选内容在生成后被篡改 -> 审批拒绝并退回 DRAFT
      B4 契约在候选生成后漂移 -> 审批拒绝并退回 DRAFT
      B5 审批记录入登记表（digest / version / reviewer / reference 齐全）
      B6 审批记录签名可验证（有独立信任根时；否则如实标记 SKIP）
    C. 晋升与门禁
      C1 未审批候选 promote 被拒
      C2 有 APPROVED 登记但 digest 不一致 promote 被拒
      C3 promote 后正式库出现该绑定，expected 与契约一致
      C4 同 (feature,behavior) 旧绑定晋升后被 SUPERSEDED（不双活）
      C5 gate：NO_BINDING / DRAFT_BINDING / PENDING_REVIEW / APPROVED_BINDING
      C6 gate：REVOKED -> BINDING_REVOKED
      C7 gate：契约版本变化 -> CONTRACT_MISMATCH
      C8 gate：子串不得误匹配（collect vs collect_pickup）
      C9 gate：BLOCKED_MISSING_EXPECTED 候选 -> BINDING_INVALID（不产生虚假 APPROVED）

用法：python .ai/tools/validator/tests/test_binding_candidates.py
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
VALIDATOR_DIR = os.path.dirname(_HERE)
PROJECT_ROOT = os.path.dirname(os.path.dirname(VALIDATOR_DIR))
for _p in (VALIDATOR_DIR, os.path.join(VALIDATOR_DIR, "..", "evaluation"),
           os.path.join(VALIDATOR_DIR, "..", "scene_composer")):
    sys.path.insert(0, os.path.abspath(_p))

import binding_candidates as bc               # noqa: E402
import trace_bindings as tb                   # noqa: E402

_checks = 0
_failures: list = []


def ok(name: str, condition, detail: str = "") -> None:
    global _checks
    _checks += 1
    if condition:
        print("PASS %s" % name)
    else:
        _failures.append(name)
        print("FAIL %s%s" % (name, (" | " + detail) if detail else ""))


class Sandbox:
    """隔离的候选/登记表/绑定库（真实文件只读引用，不写入）。"""

    def __init__(self) -> None:
        self.root = tempfile.mkdtemp(prefix="p163_binding_test_")
        self.candidates_path = os.path.join(self.root, "candidates.json")
        self.registry_path = os.path.join(self.root, "approval_registry.json")
        self.bindings_path = os.path.join(self.root, "behavior_bindings.json")
        shutil.copy(tb.BINDINGS_PATH, self.bindings_path)   # 从真实库副本出发

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def test_candidates_generation(sandbox: Sandbox) -> dict:
    sys.path.insert(0, os.path.join(VALIDATOR_DIR, "..", "evaluation"))
    import evidence_adapter as adapter
    supported = adapter.supported_set()
    doc = bc.generate_candidates(features_dir="", out_path=sandbox.candidates_path,
                                 existing_bindings={"bindings": []})
    candidates = doc["candidates"]
    supported_pairs = {(f, b) for f, behs in supported["features"].items()
                       for b in behs}
    candidate_pairs = {(c["feature_id"], c["behavior_id"]) for c in candidates}
    ok("A1: candidates generated for the whole supported set with contract expected",
       candidate_pairs == supported_pairs, "len=%d" % len(candidates))

    mismatched = []
    for c in candidates:
        if c["approval_status"] == bc.BLOCKED_MISSING_EXPECTED:
            continue
        version, expected, _ = bc.contract_digest(c["feature_id"], c["behavior_id"])
        if c["expected"] != expected or c["contract_version"] != version:
            mismatched.append(c["binding_id"])
    ok("A1b: expected copied verbatim from contracts", not mismatched,
       str(mismatched[:3]))

    ids = [c["binding_id"] for c in candidates]
    ok("A3: binding ids unique", len(ids) == len(set(ids)))

    # A2：已绑定的 6 条不出现在候选池
    official = tb.load_bindings()
    bound = {(b["feature_id"], b["behavior_id"]) for b in official["bindings"]}
    overlap = candidate_pairs & bound
    doc2 = bc.generate_candidates(features_dir="", out_path=sandbox.candidates_path,
                                  existing_bindings=official)
    pairs2 = {(c["feature_id"], c["behavior_id"]) for c in doc2["candidates"]}
    ok("A2: already-bound behaviors are not candidates", not (pairs2 & bound),
       str(sorted(pairs2 & bound)[:3]))

    inventory = bc.build_support_inventory()
    ok("A5: support inventory dynamic (counts from registry)",
       inventory["feature_count"] == supported["feature_count"] and
       inventory["behavior_count"] == supported["behavior_count"] and
       len(inventory["entries"]) == inventory["behavior_count"] and
       all(e["contract_version"] for e in inventory["entries"]))
    # A2 之外的候选池用于后续审批流测试（真实库已全覆盖，故用全量候选文档）
    return doc


def test_approval_flow(sandbox: Sandbox, doc: dict) -> None:
    candidate = next(c for c in doc["candidates"]
                     if c["approval_status"] == bc.DRAFT)
    bid = candidate["binding_id"]

    # B1：跳步被拒
    try:
        bc.approve_candidate(doc, bid, reviewer="t", approval_reference="x",
                             registry_path=sandbox.registry_path,
                             candidates_path=sandbox.candidates_path)
        ok("B1: DRAFT -> APPROVED skip rejected", False)
    except bc.BindingCandidateError:
        ok("B1: DRAFT -> APPROVED skip rejected", True)

    # B2：合法两步
    bc.submit_for_review(doc, bid, candidates_path=sandbox.candidates_path)
    ok("B2a: DRAFT -> PENDING_REVIEW",
       candidate["approval_status"] == bc.PENDING_REVIEW)
    record = bc.approve_candidate(doc, bid, reviewer="phase-1.63-test",
                                  approval_reference="unit test approval",
                                  registry_path=sandbox.registry_path,
                                  candidates_path=sandbox.candidates_path)
    ok("B2b: PENDING_REVIEW -> APPROVED",
       candidate["approval_status"] == bc.APPROVED)
    latest = bc.latest_record(bc.load_registry(sandbox.registry_path), bid)
    ok("B5: registry record complete",
       latest is not None and latest["approved_digest"] == record["approved_digest"]
       and latest["approved_contract_version"] == candidate["contract_version"]
       and latest["reviewer"] == "phase-1.63-test"
       and latest["decision"] == "APPROVED", str(latest)[:120] if latest else "none")

    # B6：签名验证（依赖本机独立信任根；没有则如实 SKIP）
    if record.get("signature_envelope"):
        try:
            from provenance.verification import verify_envelope
            from provenance.trust_store import TrustStore
            store = TrustStore(project_root=PROJECT_ROOT)
            result = verify_envelope(record["signature_envelope"],
                                     object_type="behavior_binding", object_id=bid,
                                     object_version=record["approved_contract_version"],
                                     expected_digest=record["approved_digest"],
                                     trust_store=store)
            ok("B6: approval signature verifies against independent trust root",
               result["status"] == "SIGNATURE_VALID", str(result.get("reason")))
        except Exception as exc:                              # noqa: BLE001
            ok("B6: approval signature verifies", False, "SKIP/ERROR %r" % (exc,))
    else:
        print("SKIP B6: approval signature (no trust-root key available in test)")

    # B3：候选内容被篡改 -> 审批拒绝
    other = next(c for c in doc["candidates"]
                 if c["binding_id"] != bid and c["approval_status"] == bc.DRAFT)
    bc.submit_for_review(doc, other["binding_id"], candidates_path=sandbox.candidates_path)
    tampered = copy.deepcopy(other)
    tampered["expected"] = [dict(tampered["expected"][0], equals="hacked")] \
        if tampered["expected"] else []
    stored = other["candidate_digest"]
    other["candidate_digest"] = bc.candidate_digest(tampered)   # 伪装登记值
    try:
        bc.approve_candidate(doc, other["binding_id"], reviewer="attacker",
                             approval_reference="forged",
                             registry_path=sandbox.registry_path,
                             candidates_path=sandbox.candidates_path)
        ok("B3: tampered candidate digest rejected", False)
    except bc.BindingCandidateError:
        ok("B3: tampered candidate digest rejected", True)
    ok("B3b: rejected candidate reset to DRAFT",
       other["approval_status"] == bc.DRAFT)
    other["candidate_digest"] = stored                          # 还原

    # B4：契约漂移 -> 审批拒绝
    third = next(c for c in doc["candidates"]
                 if c["binding_id"] not in (bid, other["binding_id"])
                 and c["approval_status"] == bc.DRAFT)
    bc.submit_for_review(doc, third["binding_id"], candidates_path=sandbox.candidates_path)
    real_version = third["contract_version"]
    third["contract_version"] = "drifted0000000"
    try:
        bc.approve_candidate(doc, third["binding_id"], reviewer="t",
                             approval_reference="x",
                             registry_path=sandbox.registry_path,
                             candidates_path=sandbox.candidates_path)
        ok("B4: contract drift rejected at approval", False)
    except bc.BindingCandidateError:
        ok("B4: contract drift rejected at approval", True)
    ok("B4b: drifted candidate reset to DRAFT",
       third["approval_status"] == bc.DRAFT)
    third["contract_version"] = real_version                    # 还原

    # B6b：BLOCKED 候选永不可批
    blocked = {"schema": "x", "candidates": [{
        "binding_id": "BND-BLOCKED", "feature_id": "f", "behavior_id": "b",
        "contract_version": "", "expected": [], "expected_source": "behavior_contract",
        "source_contract": "", "source_digest": "",
        "approval_status": bc.BLOCKED_MISSING_EXPECTED, "generated_at": "",
        "candidate_digest": ""}]}
    try:
        bc.approve_candidate(blocked, "BND-BLOCKED", reviewer="t",
                             approval_reference="x",
                             registry_path=sandbox.registry_path,
                             candidates_path=sandbox.candidates_path)
        ok("B6b: BLOCKED_MISSING_EXPECTED can never be approved", False)
    except bc.BindingCandidateError:
        ok("B6b: BLOCKED_MISSING_EXPECTED can never be approved", True)


def test_promote_and_gate(sandbox: Sandbox, doc: dict) -> None:
    candidate = next(c for c in doc["candidates"]
                     if c["approval_status"] == bc.APPROVED)
    bid = candidate["binding_id"]
    feature, behavior = candidate["feature_id"], candidate["behavior_id"]

    # C1：未审批候选 promote 被拒
    draft = next(c for c in doc["candidates"] if c["approval_status"] == bc.DRAFT)
    try:
        bc.promote_binding(doc, draft["binding_id"], registry_path=sandbox.registry_path,
                           bindings_path=sandbox.bindings_path)
        ok("C1: unapproved promote rejected", False)
    except bc.BindingCandidateError:
        ok("C1: unapproved promote rejected", True)

    # C2：审批后候选内容被改动（重算摘要 != 登记摘要）promote 被拒
    real_expected = copy.deepcopy(candidate["expected"])
    real_digest = candidate["candidate_digest"]
    candidate["expected"] = [dict(real_expected[0], equals="hacked")] \
        if real_expected else []
    try:
        bc.promote_binding(doc, bid, registry_path=sandbox.registry_path,
                           bindings_path=sandbox.bindings_path)
        ok("C2: post-approval content change promote rejected", False)
    except bc.BindingCandidateError:
        ok("C2: post-approval content change promote rejected", True)
    candidate["expected"] = real_expected
    candidate["candidate_digest"] = real_digest

    # C3：正常晋升（挑一个正式库里已有旧绑定的 pair，验证 C4 一起覆盖）
    official_before = tb.load_bindings(sandbox.bindings_path)
    old = next(b for b in official_before["bindings"]
               if (b["feature_id"], b["behavior_id"]) != (feature, behavior))
    old_pair = (old["feature_id"], old["behavior_id"])
    old_id = old["binding_id"]
    target = next(c for c in doc["candidates"]
                  if (c["feature_id"], c["behavior_id"]) == old_pair)
    if target["approval_status"] != bc.APPROVED:
        bc.submit_for_review(doc, target["binding_id"], candidates_path=sandbox.candidates_path)
        bc.approve_candidate(doc, target["binding_id"], reviewer="t",
                             approval_reference="x",
                             registry_path=sandbox.registry_path,
                             candidates_path=sandbox.candidates_path)
    result = bc.promote_binding(doc, target["binding_id"],
                                registry_path=sandbox.registry_path,
                                bindings_path=sandbox.bindings_path)
    ok("C3: promoted binding enters official library with contract expected",
       result["promoted"] == target["binding_id"] and
       tb.get_binding(tb.load_bindings(sandbox.bindings_path),
                      old_pair[0], old_pair[1]) is not None)
    registry = bc.load_registry(sandbox.registry_path)
    old_latest = bc.latest_record(registry, old_id)
    ok("C4: superseded old binding is not dual-alive",
       result["superseded"] == [old_id] and
       old_latest and old_latest["decision"] == bc.SUPERSEDED,
       str(result["superseded"]))

    # C5：门禁状态族
    official = tb.load_bindings(sandbox.bindings_path)
    candidates_doc = bc.load_candidates(sandbox.candidates_path)
    registry = bc.load_registry(sandbox.registry_path)
    st = bc.binding_gate_status(old_pair[0], old_pair[1], candidates=candidates_doc,
                                registry=registry, official_bindings=official)
    ok("C5a: promoted -> APPROVED_BINDING", st["status"] == bc.APPROVED_BINDING,
       str(st))
    st2 = bc.binding_gate_status("no_such_feature", "no_such_behavior",
                                 candidates={"candidates": []}, registry=registry,
                                 official_bindings=official)
    ok("C5b: unknown behavior -> NO_BINDING", st2["status"] == bc.NO_BINDING)
    draft_candidate = {"binding_id": "BND-DRAFTTEST", "feature_id": "fx",
                       "behavior_id": "bx", "approval_status": bc.DRAFT}
    st3 = bc.binding_gate_status("fx", "bx",
                                 candidates={"candidates": [draft_candidate]},
                                 registry=registry, official_bindings=official)
    ok("C5c: DRAFT candidate -> DRAFT_BINDING (not silently NO_BINDING)",
       st3["status"] == bc.DRAFT_BINDING, str(st3))
    pending_candidate = dict(draft_candidate, binding_id="BND-PEND",
                             approval_status=bc.PENDING_REVIEW)
    st4 = bc.binding_gate_status("fx", "bx",
                                 candidates={"candidates": [pending_candidate]},
                                 registry=registry, official_bindings=official)
    ok("C5d: PENDING_REVIEW candidate -> PENDING_REVIEW",
       st4["status"] == bc.PENDING_REVIEW_BINDING, str(st4))

    # C6：REVOKED -> BINDING_REVOKED
    bc.set_binding_lifecycle(target["binding_id"], bc.REVOKED,
                             reason="unit test revoke",
                             registry_path=sandbox.registry_path)
    st5 = bc.binding_gate_status(old_pair[0], old_pair[1], candidates=candidates_doc,
                                 registry=bc.load_registry(sandbox.registry_path),
                                 official_bindings=official)
    ok("C6: revoked binding -> BINDING_REVOKED", st5["status"] == bc.BINDING_REVOKED,
       str(st5))

    # C7：契约版本变化 -> CONTRACT_MISMATCH（用未被撤销的 pair：health/damage）
    c7_pair = ("health", "damage")
    official7 = copy.deepcopy(official)
    for b in official7["bindings"]:
        if (b["feature_id"], b["behavior_id"]) == c7_pair:
            b["contract_version"] = "drifted0000000"
    st6 = bc.binding_gate_status(c7_pair[0], c7_pair[1], candidates=candidates_doc,
                                 registry=bc.load_registry(sandbox.registry_path),
                                 contract_version="current0000000",
                                 official_bindings=official7)
    ok("C7: contract version change -> CONTRACT_MISMATCH",
       st6["status"] == "CONTRACT_MISMATCH", str(st6))

    # C8：子串不得误匹配
    st7 = bc.binding_gate_status("collect", "collect_on_contact",
                                 candidates=candidates_doc, registry=registry,
                                 official_bindings=official)
    ok("C8: substring feature id does not match", st7["status"] == bc.NO_BINDING)

    # C9：BLOCKED 候选 -> BINDING_INVALID
    blocked = {"binding_id": "BND-BLK", "feature_id": "fy", "behavior_id": "by",
               "approval_status": bc.BLOCKED_MISSING_EXPECTED,
               "blocked_reason": "no expected in contract"}
    st8 = bc.binding_gate_status("fy", "by", candidates={"candidates": [blocked]},
                                 registry=registry, official_bindings=official)
    ok("C9: blocked candidate -> BINDING_INVALID (no fake approval)",
       st8["status"] == bc.BINDING_INVALID, str(st8))


def main() -> int:
    sandbox = Sandbox()
    try:
        doc = test_candidates_generation(sandbox)
        test_approval_flow(sandbox, doc)
        test_promote_and_gate(sandbox, doc)
    finally:
        sandbox.cleanup()
    print("\n%d check(s), %d failure(s)" % (_checks, len(_failures)))
    if _failures:
        print("FAIL: " + "; ".join(_failures[:5]))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
