#!/usr/bin/env python3
"""Evaluation Evidence Adapter 测试（Phase 1.58）。

被测对象：`.ai/tools/evaluation/evidence_adapter.py`

覆盖矩阵：

    A. Adapter 输入/输出
      A1  合法 Validator PASS -> 逐 behavior 记录（含 run_id / 产物摘要 / 协议版本）
      A2  证据包被篡改 -> 包级 FAIL 被传播到 behavior（不因逐条复算通过而放行）
      A3  缺执行产物 -> INCOMPLETE（保留，不升级）
      A4  Validator ERROR -> 保留为 ERROR
      A5  未知 Feature -> FAIL
      A6  未声明 Behavior -> FAIL
      A7  result.json 被改写（execution_id 错配）-> FAIL
      A8  证据包缺 integrity -> FAIL，且不伪造 bundle_digest
      A9  artifact_digests / evidence_paths 原样保留
      A10 protocol_version 原样保留
      A11 旧 schema（无 evidence_paths / artifact_digests）-> INCOMPLETE
    B. 状态模型
      B1-B6 转换表六行；B7 非法转换被拒绝；B8 缺期望不升级为 PASS
    C. 任务映射
      C1 正确映射；C2 未知 Feature；C3 未知 Behavior；C4 跨 Feature 证据；
      C5 重复映射；C6 多 Behavior 任务；C7 跨批次混用；C8 支持集动态读取
    D. Evidence-backed 评估
      D1 VERIFIED_PASS；D2 证据无效 -> INVALID_EVIDENCE；D3 INCOMPLETE；
      D4 有效证据但行为不符 -> VERIFIED_FAIL；D5 观测缺失 -> INCOMPLETE；
      D6 可追溯字段齐全；D7 多任务汇总
    F. Golden Trace
      F1 已批准基线元数据；F2 未审批；F3 基线损坏；F4 基线缺失；
      F5 Expected/Actual 一致 -> PASS；F6 不一致 -> REGRESSION
    G. Holdout
      G1 同一批次两边使用 -> 违规；G2 批次独立 -> 无违规

所有 fixture 都建在 `.ai/tmp/` 下的临时目录，测试结束删除。

用法：python .ai/tools/evaluation/tests/test_evidence_adapter.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.dirname(_HERE)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(EVAL_DIR)))
for _path in (_HERE, EVAL_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import evidence_adapter as adapter                               # noqa: E402
import evidence_fixtures as fixtures                             # noqa: E402
import feature_behavior_evidence as fbe                          # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_failures: list = []
_checks = 0
_temp_dirs: list = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    global _checks
    _checks += 1
    if condition:
        print("PASS: " + name)
    else:
        _failures.append(name + (" | " + detail if detail else ""))
        print("FAIL: " + name + (" | " + detail if detail else ""))


def new_dir(prefix: str) -> str:
    base = os.path.join(PROJECT_ROOT, ".ai", "tmp")
    os.makedirs(base, exist_ok=True)
    directory = tempfile.mkdtemp(prefix=prefix, dir=base)
    _temp_dirs.append(directory)
    return directory


def cleanup() -> None:
    for directory in _temp_dirs:
        shutil.rmtree(directory, ignore_errors=True)


def bundle_path(evidence_dir: str, name: str = "bundle-test.json") -> str:
    return os.path.join(evidence_dir, name)


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str, document: dict) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


FEATURES_IN_FIXTURE = ["collect_pickup", "health"]


def verified_of(evidence_dir: str, artifact_root: str, **kwargs) -> dict:
    """按 fixture 实际覆盖的 Feature 限定验证范围（否则其余 21 个 Feature 全为 INCOMPLETE）。"""
    kwargs.setdefault("features", FEATURES_IN_FIXTURE)
    return adapter.load_verified(evidence_dir=evidence_dir,
                                 artifact_roots=[artifact_root], **kwargs)


def behavior_of(verified: dict, feature: str, behavior: str) -> dict:
    for item in verified.get("behaviors") or []:
        if item["feature"] == feature and item["behavior"] == behavior:
            return item
    return {}


# 证据必须覆盖被测 Feature 声明的**全部**行为，否则 Validator 报 behavior_uncovered。
PAIRS = fixtures.feature_pairs(["collect_pickup", "health"])


# ------------------------------------------------------------------ A 段
def test_adapter_inputs() -> dict:
    root = new_dir("eval158-clean-")
    clean_dir, clean_artifacts = fixtures.make_evidence_dir(root, PAIRS)
    verified = verified_of(clean_dir, clean_artifacts)
    clean_item = behavior_of(verified, "collect_pickup", "collect_on_contact")

    ok("A1: validator PASS on a well-formed bundle",
       verified["validator"]["status"] == "PASS",
       json.dumps(verified["validator"].get("detail"))[:200])
    ok("A1: behaviors carry validator verdicts",
       len(verified["behaviors"]) == len(PAIRS)
       and all(item["validator_status"] == "PASS" for item in verified["behaviors"]),
       str([(item["behavior"], item["validator_status"]) for item in verified["behaviors"]]))
    ok("A1: execution id preserved",
       bool(clean_item.get("execution", {}).get("run_id")), str(clean_item.get("execution"))[:200])
    ok("A9: artifact digests preserved",
       bool(clean_item.get("execution", {}).get("artifact_digests")))
    ok("A9: evidence paths preserved",
       bool(clean_item.get("execution", {}).get("evidence_paths")))
    ok("A10: protocol version preserved",
       str(clean_item.get("execution", {}).get("protocol_version")) == str(fixtures.PROTOCOL.version),
       str(clean_item.get("execution", {}).get("protocol_version")))
    ok("A10: bundle digest matches the bundle integrity block",
       clean_item.get("execution", {}).get("bundle_digest")
       == load_json(bundle_path(clean_dir))["integrity"]["payload_sha256"])

    # A2：只改证据内容、不重签 -> 包级 FAIL 必须传播到 behavior
    tampered_root = new_dir("eval158-tamper-")
    tampered_dir, tampered_artifacts = fixtures.make_evidence_dir(tampered_root, PAIRS,
                                                                 bundle_id="bundle-tampered")
    document = load_json(bundle_path(tampered_dir, "bundle-tampered.json"))
    document["features"][0]["behaviors"][0]["actual"][0]["observed"] = False
    write_json(bundle_path(tampered_dir, "bundle-tampered.json"), document)
    tampered = verified_of(tampered_dir, tampered_artifacts)
    tampered_item = behavior_of(tampered, "collect_pickup", "collect_on_contact")
    ok("A2: tampered bundle is rejected by the validator",
       tampered["validator"]["status"] == "FAIL", str(tampered["validator"].get("detail"))[:160])
    ok("A2: bundle-level FAIL is propagated to every behavior in that bundle",
       tampered_item.get("validator_status") == "FAIL"
       and tampered_item.get("validator_reason") == "bundle_rejected",
       str(tampered_item.get("validator_status")) + "/" + str(tampered_item.get("validator_reason")))

    # A3：缺执行产物 -> INCOMPLETE
    missing_root = new_dir("eval158-missing-")
    missing_dir, missing_artifacts = fixtures.make_evidence_dir(
        missing_root, PAIRS, bundle_id="bundle-missing", omit_artifacts=True)
    missing = verified_of(missing_dir, missing_artifacts)
    missing_item = behavior_of(missing, "health", "damage")
    ok("A3: missing artifacts keep INCOMPLETE",
       missing_item.get("validator_status") == "INCOMPLETE",
       str(missing_item.get("validator_reason")))

    # A4：协议文件非法 -> ERROR
    bad_protocol = os.path.join(root, "bad_protocol.yaml")
    with open(bad_protocol, "w", encoding="utf-8") as handle:
        handle.write("not: [a, protocol]\n")
    errored = verified_of(clean_dir, clean_artifacts, protocol_path=bad_protocol)
    ok("A4: validator ERROR is preserved",
       errored["validator"]["status"] == "ERROR", str(errored["validator"].get("status")))

    # A5：未知 Feature
    unknown_root = new_dir("eval158-unknown-feature-")
    unknown_dir = os.path.join(unknown_root, "bundles")
    record = fixtures.behavior_record("collect_pickup", "collect_on_contact",
                                      os.path.join(unknown_root, "artifacts"))
    record["feature"] = "ghost_feature"
    ghost = fixtures.build_bundle([{"feature": "ghost_feature", "evidence_level": "L4",
                                    "behaviors": [record]}], bundle_id="bundle-ghost")
    fixtures.write_bundle(unknown_dir, ghost)
    unknown = verified_of(unknown_dir, os.path.join(unknown_root, "artifacts"))
    ghost_item = behavior_of(unknown, "ghost_feature", "collect_on_contact")
    ok("A5: unknown feature is rejected",
       unknown["validator"]["status"] == "FAIL"
       and ghost_item.get("validator_reason") == "unknown_feature",
       str(ghost_item.get("validator_reason")))

    # A6：未声明 Behavior
    undeclared_root = new_dir("eval158-unknown-behavior-")
    undeclared_dir, undeclared_artifacts = fixtures.make_evidence_dir(
        undeclared_root, PAIRS, bundle_id="bundle-undeclared")
    document = load_json(bundle_path(undeclared_dir, "bundle-undeclared.json"))
    document["features"][0]["behaviors"][0]["behavior"] = "ghost_behavior"
    fixtures.resign_bundle(document)
    write_json(bundle_path(undeclared_dir, "bundle-undeclared.json"), document)
    undeclared = verified_of(undeclared_dir, undeclared_artifacts)
    ghost_behavior = behavior_of(undeclared, "collect_pickup", "ghost_behavior")
    ok("A6: undeclared behavior is rejected",
       undeclared["validator"]["status"] == "FAIL"
       and ghost_behavior.get("validator_reason") == "unknown_behavior",
       str(ghost_behavior.get("validator_reason")))

    # A7：result.json 被改写（execution_id 错配）
    artifact_root = new_dir("eval158-artifact-")
    artifact_dir, artifact_artifacts = fixtures.make_evidence_dir(
        artifact_root, PAIRS, bundle_id="bundle-artifact")
    item = behavior_of(verified_of(artifact_dir, artifact_artifacts),
                       "collect_pickup", "collect_on_contact")
    first_run = sorted(item["execution"]["evidence_paths"])[0]
    result_file = item["execution"]["evidence_paths"][first_run]["result"]
    payload = load_json(result_file)
    payload["run_id"] = "rewritten-run-id"
    write_json(result_file, payload)
    rewritten = verified_of(artifact_dir, artifact_artifacts)
    rewritten_item = behavior_of(rewritten, "collect_pickup", "collect_on_contact")
    ok("A7: rewritten result.json is rejected",
       rewritten_item.get("validator_status") == "FAIL",
       str(rewritten_item.get("validator_reason")))

    # A8：缺 integrity -> FAIL，且不伪造 digest
    no_integrity_root = new_dir("eval158-no-integrity-")
    no_integrity_dir, no_integrity_artifacts = fixtures.make_evidence_dir(
        no_integrity_root, PAIRS, bundle_id="bundle-no-integrity")
    document = load_json(bundle_path(no_integrity_dir, "bundle-no-integrity.json"))
    document.pop("integrity", None)
    write_json(bundle_path(no_integrity_dir, "bundle-no-integrity.json"), document)
    no_integrity = verified_of(no_integrity_dir, no_integrity_artifacts)
    no_integrity_item = behavior_of(no_integrity, "health", "damage")
    ok("A8: bundle without integrity is rejected",
       no_integrity["validator"]["status"] == "FAIL"
       and no_integrity_item.get("validator_status") == "FAIL")
    ok("A8: no digest is fabricated when integrity is absent",
       no_integrity_item.get("execution", {}).get("bundle_digest") is None)

    # A11：旧 schema（无 evidence_paths / artifact_digests）
    legacy_root = new_dir("eval158-legacy-")
    legacy_dir, legacy_artifacts = fixtures.make_evidence_dir(
        legacy_root, PAIRS, bundle_id="bundle-legacy", legacy=True)
    legacy = verified_of(legacy_dir, legacy_artifacts)
    legacy_item = behavior_of(legacy, "collect_pickup", "collect_on_contact")
    ok("A11: legacy records without artifacts stay INCOMPLETE",
       legacy_item.get("validator_status") == "INCOMPLETE",
       str(legacy_item.get("validator_reason")))

    return {"verified": verified, "clean_dir": clean_dir, "artifacts": clean_artifacts}


# ------------------------------------------------------------------ B 段
def test_status_model() -> None:
    cases = [
        ("PASS", adapter.EXPECTATION_MET, adapter.VERIFIED_PASS),
        ("PASS", adapter.EXPECTATION_UNMET, adapter.VERIFIED_FAIL),
        ("PASS", adapter.EXPECTATION_UNDECIDABLE, adapter.INCOMPLETE),
        ("FAIL", adapter.EXPECTATION_MET, adapter.INVALID_EVIDENCE),
        ("INCOMPLETE", adapter.EXPECTATION_MET, adapter.INCOMPLETE),
        ("ERROR", adapter.EXPECTATION_MET, adapter.EVALUATION_ERROR),
    ]
    for index, (validator, state, expected) in enumerate(cases, start=1):
        status, reason = adapter.evaluation_status(validator, state)
        ok("B%d: %s + %s -> %s" % (index, validator, state, expected),
           status == expected, "%s (%s)" % (status, reason))
    ok("B7: illegal transition is rejected",
       adapter.evaluation_status("SOMETHING", adapter.EXPECTATION_MET)
       == (adapter.EVALUATION_ERROR, "illegal_transition"))
    ok("B7: empty validator status is rejected",
       adapter.evaluation_status("", adapter.EXPECTATION_MET)[0] == adapter.EVALUATION_ERROR)
    ok("B8: PASS without expectation never becomes VERIFIED_PASS",
       adapter.evaluation_status("PASS", None)
       == (adapter.EVALUATION_ERROR, "expectation_missing"))


# ------------------------------------------------------------------ C/D 段
def test_mapping_and_evaluation(context: dict) -> None:
    verified = context["verified"]
    supported = adapter.supported_set()

    task = {"id": "C1", "feature": "collect_pickup", "behavior": "collect_on_contact",
            "expect": [{"check": "node.freed", "target": ".", "equals": True}]}
    record = adapter.evaluate_task(task, verified, supported)
    ok("C1: correct mapping evaluates to VERIFIED_PASS",
       record["evaluation_status"] == adapter.VERIFIED_PASS, str(record.get("detail"))[:160])
    ok("D1: verified pass carries execution identity",
       record["behaviors"][0].get("execution_id") and record["behaviors"][0].get("bundle_digest"))
    ok("D6: evidence reference is complete",
       record["behaviors"][0].get("evidence_bundle_ref", "").startswith("bundle-test.json#"),
       str(record["behaviors"][0].get("evidence_bundle_ref")))

    unknown_feature = adapter.evaluate_task(
        {"id": "C2", "feature": "ghost_feature", "behavior": "collect_on_contact",
         "expect": []}, verified, supported)
    ok("C2: unknown feature is refused",
       unknown_feature["evaluation_status"] == adapter.EVALUATION_ERROR
       and unknown_feature["reason"] == "unknown_feature")

    unknown_behavior = adapter.evaluate_task(
        {"id": "C3", "feature": "collect_pickup", "behavior": "ghost_behavior",
         "expect": []}, verified, supported)
    ok("C3: unknown behavior is refused",
       unknown_behavior["evaluation_status"] == adapter.EVALUATION_ERROR
       and unknown_behavior["reason"] == "unknown_behavior")

    # C4：把「只有 collect_pickup 证据」的结论拿去评估 health —— 不得跨 Feature 复用
    collect_only = adapter.load_verified(
        evidence_dir=context["clean_dir"], features=["collect_pickup"],
        artifact_roots=[context["artifacts"]])
    cross = adapter.evaluate_task(
        {"id": "C4", "feature": "health", "behavior": "heal_clamped",
         "expect": [{"check": "health.current", "target": ".", "min": 0}]},
        collect_only, supported)
    ok("C4: cross-feature evidence is not reused",
       cross["evaluation_status"] == adapter.INCOMPLETE
       and cross["reason"] == "no_evidence", str(cross.get("reason")))

    duplicates = adapter.duplicate_mappings([
        {"id": "C5a", "feature": "health", "behavior": "damage"},
        {"id": "C5b", "feature": "health", "behavior": "damage"},
    ])
    ok("C5: duplicate mapping is detected", len(duplicates) == 1, str(duplicates))

    multi = adapter.evaluate_task(
        {"id": "C6", "feature": "health",
         "behaviors": [{"behavior": "damage",
                        "expect": [{"check": "health.current", "target": ".", "equals": 1}]},
                       {"behavior": "heal_clamped",
                        "expect": [{"check": "health.current", "target": ".", "equals": 999}]}]},
        verified, supported)
    statuses = [(item["behavior"], item["evaluation_status"]) for item in multi["behaviors"]]
    ok("C6: multi-behavior task folds to the worst status",
       multi["evaluation_status"] == adapter.VERIFIED_FAIL
       and dict(statuses).get("damage") == adapter.VERIFIED_PASS, str(statuses))

    strict = adapter.evaluate_task(
        {"id": "D4", "feature": "health", "behavior": "damage",
         "expect": [{"check": "health.current", "target": ".", "equals": 99}]},
        verified, supported)
    ok("D4: valid evidence with unmet expectation is VERIFIED_FAIL",
       strict["evaluation_status"] == adapter.VERIFIED_FAIL,
       str(strict.get("detail"))[:160])

    undecidable = adapter.evaluate_task(
        {"id": "D5", "feature": "health", "behavior": "damage",
         "expect": [{"check": "no.such.check", "target": ".", "equals": 1}]},
        verified, supported)
    ok("D5: missing observation yields INCOMPLETE",
       undecidable["evaluation_status"] == adapter.INCOMPLETE
       and undecidable["reason"] == "expectation_undecidable")

    empty_expect = adapter.evaluate_task(
        {"id": "D5b", "feature": "health", "behavior": "damage", "expect": []},
        verified, supported)
    ok("D5b: task without expectation is not a pass",
       empty_expect["evaluation_status"] == adapter.INCOMPLETE)

    summary = adapter.summarize([record, strict, undecidable], verified,
                                supported=supported)
    ok("D7: summary counts by status",
       summary["behavior_evaluation"]["VERIFIED_PASS"] == 1
       and summary["behavior_evaluation"]["VERIFIED_FAIL"] == 1
       and summary["behavior_evaluation"]["INCOMPLETE"] == 1,
       json.dumps(summary["behavior_evaluation"]))
    ok("D7: summary keeps evidence validation separate",
       summary["evidence_validation"]["pass"] == len(PAIRS),
       json.dumps(summary["evidence_validation"]))
    ok("C8: supported set is read dynamically, not hardcoded",
       supported["feature_count"] == len(fbe.declared_features(fixtures.FEATURES))
       and supported["behavior_count"]
       == sum(len(fixtures.contracts_of(name)) for name in supported["features"]),
       "%s/%s" % (supported["feature_count"], supported["behavior_count"]))

    # D2/D3：把其它证据目录的结论接进同一个任务
    fail_task = adapter.evaluate_task(task, {"behaviors": [
        dict(verified["behaviors"][0], validator_status="FAIL")]}, supported)
    ok("D2: invalid evidence becomes INVALID_EVIDENCE",
       fail_task["evaluation_status"] == adapter.INVALID_EVIDENCE)
    incomplete_task = adapter.evaluate_task(task, {"behaviors": [
        dict(verified["behaviors"][0], validator_status="INCOMPLETE")]}, supported)
    ok("D3: incomplete evidence never passes",
       incomplete_task["evaluation_status"] == adapter.INCOMPLETE)


# ------------------------------------------------------------------ F 段
def test_golden_trace() -> None:
    baseline_path = os.path.join(adapter.VALIDATOR_DIR, "baselines", "waves.json")
    report = adapter.baseline_report(path=baseline_path)
    ok("F1: approved baseline metadata is reported",
       report["status"] == "PASS" and report["approval_status"] == "approved",
       json.dumps(report)[:200])
    ok("F1: baseline binds a scenario, not a Feature/Behavior",
       report["binding"] == "scenario_only" and report["feature"] is None
       and report["behavior"] is None)
    ok("F1: baseline version is recorded",
       isinstance(report["baseline_version"], int) and report["baseline_version"] >= 1)

    root = new_dir("eval158-baseline-")
    unapproved = load_json(baseline_path)
    unapproved["approval"] = dict(unapproved.get("approval") or {}, status="pending")
    unapproved_path = os.path.join(root, "unapproved.json")
    write_json(unapproved_path, unapproved)
    ok("F2: unapproved baseline is refused",
       adapter.baseline_report(path=unapproved_path)["status"] == "BASELINE_UNAPPROVED")

    broken_path = os.path.join(root, "broken.json")
    write_json(broken_path, {"document": "not_a_baseline"})
    ok("F3: corrupt baseline is INVALID_BASELINE",
       adapter.baseline_report(path=broken_path)["status"] == "INVALID_BASELINE")

    ok("F4: missing baseline is INCOMPLETE",
       adapter.baseline_report(path=os.path.join(root, "nope.json"))["status"]
       == adapter.INCOMPLETE)

    baseline = load_json(baseline_path)
    run_id = "eval158-replay"
    events = []
    for index, event in enumerate(baseline["events"]):
        item = dict(event)
        item["run_id"] = run_id
        item["sequence"] = index
        events.append(item)
    trace = {"document": "orchestration_trace", "schema_version": 1, "run_id": run_id,
             "events": events, "event_count": len(events), "dropped_events": 0}
    trace_path = os.path.join(root, "trace.json")
    write_json(trace_path, trace)
    matched = adapter.compare_with_baseline(baseline_path, trace_path)
    ok("F5: matching trace passes the approved baseline",
       matched["status"] == "PASS" and matched["matched_event_count"] == len(events),
       json.dumps({key: matched.get(key) for key in ("status", "matched_event_count",
                                                    "differences")})[:240])

    mutated = json.loads(json.dumps(trace))
    mutated["events"][-1]["reason"] = "eval158_mutated_reason"
    mutated_path = os.path.join(root, "trace_mutated.json")
    write_json(mutated_path, mutated)
    differing = adapter.compare_with_baseline(baseline_path, mutated_path)
    ok("F6: divergent trace is reported as a regression",
       differing["status"] in ("REGRESSION", "INVALID_TRACE")
       and bool(differing["differences"]),
       str(differing["status"]) + " " + json.dumps(differing.get("first_difference"))[:200])


# ------------------------------------------------------------------ G 段
def test_holdout(context: dict) -> None:
    verified = context["verified"]
    ok("G1: reusing the same batch for training and holdout is flagged",
       len(adapter.holdout_isolation(verified, verified)) >= 1,
       str(adapter.holdout_isolation(verified, verified))[:200])

    root = new_dir("eval158-holdout-")
    holdout_dir, holdout_artifacts = fixtures.make_evidence_dir(
        root, PAIRS, bundle_id="holdout-bundle", run_id_suffix="-holdout")
    holdout_verified = verified_of(holdout_dir, holdout_artifacts)
    ok("G2: disjoint batches pass the isolation check",
       adapter.holdout_isolation(verified, holdout_verified) == [],
       str(adapter.holdout_isolation(verified, holdout_verified))[:200])


def main() -> int:
    context = test_adapter_inputs()
    test_status_model()
    test_mapping_and_evaluation(context)
    test_golden_trace()
    test_holdout(context)
    cleanup()
    print("\n%d check(s), %d failure(s)" % (_checks, len(_failures)))
    if _failures:
        print("FAIL: " + "; ".join(_failures[:5]))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
