#!/usr/bin/env python3
"""Phase 1.68.2：官方 Contract 覆盖维度测试（不启动 Godot）。"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
EVALUATION = os.path.dirname(HERE)
TOOLS = os.path.dirname(EVALUATION)
sys.path[:0] = [EVALUATION, TOOLS, os.path.join(TOOLS, "validator"),
                os.path.join(TOOLS, "scene_composer"),
                os.path.join(TOOLS, "validator", "execution")]

import coverage_matrix as cm  # noqa: E402
import feature_behavior_evidence as fbe  # noqa: E402
import binding_candidates as bc  # noqa: E402

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


def record(**overrides) -> dict:
    base = {"feature_id": "f", "behavior_id": "b", "run_id": "r", "bundle_path": "",
            "execution_status": "PASSED", "evidence_status": "EVIDENCE_VERIFIED",
            "attestation_status": "ATTESTED_VERIFIED",
            "official_contract_status": "PASS", "official_evaluation_status": "PASS",
            "official_coverage_status": "OFFICIAL_PASS", "detail": ""}
    base.update(overrides)
    return base


def _fixture(tmp: str, *, mutate_block=None, mutate_actual=None,
             drop_block: bool = False, reseal: bool = True) -> dict:
    """构造一个可被覆盖维度读取的官方 Bundle；不生成签名。"""
    version, _expected, core = bc.contract_digest("openable_door", "open", "Features")
    expected = fbe.build_contracts("openable_door", "Features")[0][0]["expected"]
    actual = [
        {"check": "door.is_open", "target": ".", "observed": True},
        {"check": "signal", "target": ".", "entry": "door.state_changed",
         "observed": 1, "observed_args": []},
    ]
    if mutate_actual:
        mutate_actual(actual)
    block = {
        "schema": "official_contract_execution", "schema_version": 1,
        "kind": "OFFICIAL_CONTRACT", "behavior": "openable_door/open",
        "feature_id": "openable_door", "behavior_id": "open",
        "contract_version": version,
        "contract_digest": hashlib.sha256(core.encode("utf-8")).hexdigest(),
        "contract_expected": expected, "contract_actions": [],
        "judge_version": "keyed-v1", "judge_status": "PASS",
        "judge_digest": "",
        "observation_digest": hashlib.sha256(
            fbe.canonical_json(actual).encode("utf-8")).hexdigest(),
        "observations": actual,
    }
    if mutate_block:
        mutate_block(block)
    bundle = {
        "schema": "feature_behavior_evidence_bundle", "schema_version": 1,
        "bundle_id": "fixture", "generated_at": "2026-01-01T00:00:00Z",
        "features": [{"feature": "openable_door", "behaviors": [{
            "feature": "openable_door", "behavior": "open", "status": "PASS",
            "evidence": fbe.EVIDENCE_BEHAVIOR, "action_executed": True,
            "replay_count": 2, "replay_consistent": True, "actual": actual,
        }]}],
    }
    if not drop_block:
        bundle["official_contract"] = block
    bundle["integrity"] = {"algorithm": "sha256",
                          "payload_sha256": fbe.bundle_digest(bundle)}
    path = os.path.join(tmp, "fixture-bundle.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(bundle, handle, ensure_ascii=False, indent=2, sort_keys=True)
    return {"feature_id": "openable_door", "behavior_id": "open",
            "run_id": "fixture", "bundle_path": path,
            "execution_status": "PASSED", "evidence_status": "EVIDENCE_VERIFIED",
            "attestation_status": "ATTESTED_VERIFIED",
            "official_contract_status": "PASS", "official_evaluation_status": "PASS",
            "official_coverage_status": "OFFICIAL_PASS", "detail": ""}


def main() -> int:
    no_record = cm.official_contract_dimension("f", "b", {}, "Features")
    ok("C1: no official execution is not coverage",
       no_record["status"] == "NO_OFFICIAL_EXECUTION" and not no_record["executed"])

    failed = cm.official_contract_dimension(
        "f", "b", {("f", "b"): record(execution_status="FAILED")}, "Features")
    ok("C2: failed official execution is not coverage",
       failed["status"] == "OFFICIAL_EXECUTION_FAILED" and failed["executed"])

    keyed_fail = cm.official_contract_dimension(
        "f", "b", {("f", "b"): record(official_contract_status="FAIL",
                                      official_evaluation_status="FAIL")}, "Features")
    ok("C3: keyed FAIL is not coverage",
       keyed_fail["status"] == "OFFICIAL_FAIL")

    keyed_incomplete = cm.official_contract_dimension(
        "f", "b", {("f", "b"): record(official_contract_status="INCOMPLETE",
                                      official_evaluation_status="INCOMPLETE")},
        "Features")
    ok("C4: keyed INCOMPLETE is not coverage",
       keyed_incomplete["status"] == "OFFICIAL_INCOMPLETE")

    untrusted = cm.official_contract_dimension(
        "f", "b", {("f", "b"): record()}, "Features")
    ok("C5: a self-declared PASS without a bundle is not coverage",
       untrusted["status"] == "OFFICIAL_EVIDENCE_INVALID")

    missing_attestation = cm.official_contract_dimension(
        "f", "b", {("f", "b"): record(attestation_status="NOT_ATTESTED")}, "Features")
    ok("C6: missing attestation is not coverage",
       missing_attestation["status"] == "OFFICIAL_ATTESTATION_INVALID")
    failed_attestation = cm.official_contract_dimension(
        "f", "b", {("f", "b"): record(attestation_status="SIGNATURE_INVALID")},
        "Features")
    ok("C6b: failed attestation verification is not coverage",
       failed_attestation["status"] == "OFFICIAL_ATTESTATION_INVALID")

    # 原有 fully_covered 公式不含 official_contract：官方 PASS 不能独自提升它。
    row = {
        "feature_id": "f", "behavior_id": "b",
        "contract_status": "CONTRACT_PRESENT",
        "binding": {"status": "NO_BINDING"},
        "evidence": {"status": "NO_EVIDENCE"},
        "signature": {"status": "NO_SIGNATURE"},
        "attestation": {"status": "NO_ATTESTATION"},
        "evaluation": {"status": "NOT_EVALUATED"},
        "holdout": {"status": "NO_HOLDOUT"},
        "mutation": {"status": "NOT_TESTED"},
        "official_contract": {"status": "OFFICIAL_PASS", "executed": True,
                              "attestation_status": "ATTESTED_VERIFIED"},
        "missing_requirements": ["approved_binding"],
        "next_recommended_action": "",
    }
    summary = cm.build_summary({"feature_count": 1, "behavior_count": 1,
                                "source": "test"}, [row])
    ok("C7: official PASS is counted independently",
       summary["official_contract_passed"] == 1 and
       summary["official_contract_fully_covered"] == 1)
    ok("C8: existing fully_covered formula is unchanged",
       summary["fully_covered"] == 0)

    def summary_row(status: str, executed: bool = True) -> dict:
        return {
            "feature_id": "f", "behavior_id": status,
            "contract_status": "CONTRACT_PRESENT",
            "binding": {"status": "NO_BINDING"},
            "evidence": {"status": "NO_EVIDENCE"},
            "signature": {"status": "NO_SIGNATURE"},
            "attestation": {"status": "NO_ATTESTATION"},
            "evaluation": {"status": "NOT_EVALUATED"},
            "holdout": {"status": "NO_HOLDOUT"},
            "mutation": {"status": "NOT_TESTED"},
            "official_contract": {"status": status, "executed": executed,
                                  "attestation_status": "ATTESTED_VERIFIED"},
            "missing_requirements": ["approved_binding"],
            "next_recommended_action": "",
        }

    status_rows = [summary_row("OFFICIAL_PASS"),
                   summary_row("OFFICIAL_FAIL"),
                   summary_row("OFFICIAL_INCOMPLETE"),
                   summary_row("OFFICIAL_EVIDENCE_INVALID"),
                   summary_row("OFFICIAL_ATTESTATION_INVALID"),
                   summary_row("NO_OFFICIAL_EXECUTION", executed=False)]
    status_summary = cm.build_summary(
        {"feature_count": 1, "behavior_count": len(status_rows), "source": "test"},
        status_rows)
    ok("C13: invalid evidence and attestation have independent counters",
       status_summary["official_contract_evidence_invalid"] == 1 and
       status_summary["official_contract_attestation_invalid"] == 1)
    ok("C14: PASS/FAIL/INCOMPLETE/NOT_DECIDED remain distinct",
       status_summary["official_contract_passed"] == 1 and
       status_summary["official_contract_failed"] == 1 and
       status_summary["official_contract_incomplete"] == 1 and
       status_summary["official_contract_not_decided"] == 1)
    ok("C15: only complete official PASS increases official fully covered",
       status_summary["official_contract_fully_covered"] == 1 and
       status_summary["fully_covered"] == 0)

    tmp_root = os.path.join(os.path.dirname(TOOLS), "tmp")
    os.makedirs(tmp_root, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=tmp_root) as tmp:
        missing_block = _fixture(tmp, drop_block=True)
        verdict = cm.official_contract_dimension(
            "openable_door", "open", {("openable_door", "open"): missing_block},
            "Features")
        ok("C9: bundle without official block is invalid",
           verdict["status"] == "OFFICIAL_EVIDENCE_INVALID")

        changed_actual = _fixture(tmp)
        with open(changed_actual["bundle_path"], encoding="utf-8") as handle:
            tampered = json.load(handle)
        tampered["features"][0]["behaviors"][0]["actual"][0]["observed"] = False
        with open(changed_actual["bundle_path"], "w", encoding="utf-8") as handle:
            json.dump(tampered, handle, ensure_ascii=False, sort_keys=True)
        verdict = cm.official_contract_dimension(
            "openable_door", "open", {("openable_door", "open"): changed_actual},
            "Features")
        ok("C10: changed observation is detected",
           verdict["status"] == "OFFICIAL_EVIDENCE_INVALID")

        wrong_behavior = _fixture(
            tmp, mutate_block=lambda block: block.update({"behavior": "other/x"}))
        verdict = cm.official_contract_dimension(
            "openable_door", "open", {("openable_door", "open"): wrong_behavior},
            "Features")
        ok("C11: behavior reference mismatch is rejected",
           verdict["status"] == "OFFICIAL_EVIDENCE_INVALID")

        wrong_contract = _fixture(
            tmp, mutate_block=lambda block: block.update(
                {"contract_digest": "0" * 64}))
        verdict = cm.official_contract_dimension(
            "openable_door", "open", {("openable_door", "open"): wrong_contract},
            "Features")
        ok("C12: contract reference mismatch is rejected",
           verdict["status"] == "OFFICIAL_CONTRACT_MISMATCH")

    print("\n===== test_official_contract_coverage: %d checks, %d failures ====="
          % (checks, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
