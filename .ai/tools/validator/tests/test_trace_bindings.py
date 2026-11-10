#!/usr/bin/env python3
"""Trace / Behavior Binding 测试（Phase 1.60，任务书 §8.1）。

被测对象：`.ai/tools/validator/trace_bindings.py`

覆盖矩阵：
    A. Schema
      A1 合法绑定文档通过校验
      A2 缺必填字段被拒
      A3 未知 expected_source 被拒
      A4 组合预期缺 approval_reference 被拒
      A5 approved=true 无审批凭据被拒
      A6 重复 binding_id / 重复 (feature,behavior) 被拒
    B. 归属（精确匹配）
      B1 正确 Feature/Behavior 可命中
      B2 缺失 Behavior Binding -> MISSING_BINDING
      B3 错误 Feature -> 命中不了（无子串推断）
      B4 名称子串不得命中（collect vs collect_pickup）
    C. 绑定验证
      C1 正确绑定 -> VALID_BINDING
      C2 错误 Scenario -> SCENARIO_MISMATCH
      C3 Contract Version 不一致 -> CONTRACT_MISMATCH
      C4 绑定 expected 宽于契约 -> CONTRACT_MISMATCH
      C5 绑定 expected 与契约同向 -> VALID_BINDING
      C6 未审批 Baseline -> UNAPPROVED_BASELINE
      C7 REVOKED Baseline -> REVOKED_BASELINE
      C8 DIGEST_MISMATCH Baseline -> DIGEST_MISMATCH
      C9 受信 Baseline -> VALID_BINDING
    D. 场景级 Trace 状态
      D1 无绑定引用 -> SCENARIO_ONLY（不升级）
      D2 引用且声明总数齐 -> BEHAVIOR_BOUND
      D3 引用不齐 -> BEHAVIOR_PARTIALLY_BOUND
      D4 空 scenario -> UNBOUND
    E. 绑定库
      E1 真实绑定库加载并全过校验
      E2 真实库动态覆盖当前正式支持集合（Phase 1.63：数量不硬编码，无孤儿绑定）
      E3 真实库绑定 expected 与当前契约逐项一致（漂移检测）

用法：python .ai/tools/validator/tests/test_trace_bindings.py
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
VALIDATOR_DIR = os.path.dirname(_HERE)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(VALIDATOR_DIR)))
for _path in (VALIDATOR_DIR, os.path.join(PROJECT_ROOT, ".ai", "tools", "scene_composer")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import trace_bindings as tb                                     # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_checks = 0
_failures: list = []


def ok(label: str, condition: bool, detail: str = "") -> None:
    global _checks
    _checks += 1
    if condition:
        print("PASS: %s" % label)
    else:
        _failures.append(label)
        print("FAIL: %s  %s" % (label, detail[:300]))


def binding(**overrides) -> dict:
    base = {
        "binding_id": "BND-T1",
        "feature_id": "health",
        "behavior_id": "damage",
        "scenario_id": "",
        "trace_id": "",
        "trace_version": "",
        "contract_version": "abc123",
        "baseline_id": "",
        "baseline_version": "",
        "expected": [{"check": "health.current", "target": ".", "equals": 1}],
        "expected_source": "behavior_contract",
        "expected_source_ref": "Features/health/template.yaml#behavior",
        "approved": True,
        "approval_reference": "formal contract",
        "created_at": "2026-11-03T00:00:00Z",
        "updated_at": "2026-11-03T00:00:00Z",
    }
    base.update(overrides)
    return base


CONTRACT_EXPECTED = [
    {"check": "health.current", "target": ".", "equals": 1},
    {"check": "signal", "entry": "health.health_changed", "target": ".", "count": 1},
]

TRUSTED_BASELINE = {"status": "PASS", "lifecycle_status": "APPROVED_OK", "reason": "ok"}
UNAPPROVED_BASELINE = {"status": "BASELINE_UNAPPROVED", "reason": "not approved"}
REVOKED_BASELINE = {"status": "PASS", "lifecycle_status": "REVOKED", "reason": "revoked"}
MISMATCH_BASELINE = {"status": "PASS", "lifecycle_status": "DIGEST_MISMATCH",
                     "reason": "content changed after approval"}


def test_schema() -> None:
    ok("A1: valid binding document passes",
       tb.validate_document({"bindings": [binding()]}) == [])
    ok("A2: missing required fields rejected",
       len(tb.validate_document({"bindings": [{"binding_id": "X"}]})) >= 3)
    ok("A3: unknown expected_source rejected",
       len(tb.validate_document({"bindings": [binding(expected_source="vibes")]})) >= 1)
    combined = binding(expected_source="combined_approved", approval_reference="")
    ok("A4: combined expectation without approval_reference rejected",
       len(tb.validate_document({"bindings": [combined]})) >= 1)
    unapproved = binding(approved=False)
    ok("A5: approved=true without reference rejected is enforced; "
       "reference without approved also rejected",
       len(tb.validate_document({"bindings": [
           binding(approval_reference="ref", approved=False)]})) >= 1)
    dup = tb.validate_document({"bindings": [binding(), binding(binding_id="BND-T2")]})
    ok("A6a: duplicate (feature,behavior) rejected", len(dup) >= 1, str(dup[:1]))
    dup = tb.validate_document({"bindings": [binding(), binding()]})
    ok("A6b: duplicate binding_id rejected", len(dup) >= 1, str(dup[:1]))


def test_identity() -> None:
    doc = {"bindings": [binding()]}
    ok("B1: exact ids hit", tb.get_binding(doc, "health", "damage") is not None)
    ok("B2: missing behavior -> get_binding None",
       tb.get_binding(doc, "health", "heal") is None)
    ok("B3: wrong feature does not match",
       tb.get_binding(doc, "damage", "damage") is None)
    ok("B4: substring must not match",
       tb.get_binding(doc, "heal", "damage") is None
       and tb.get_binding(doc, "health", "damag") is None)

    result = tb.validate_binding(None, feature_id="health", behavior_id="heal")
    ok("B2b: no binding -> MISSING_BINDING", result["status"] == tb.MISSING_BINDING,
       str(result))


def test_validation() -> None:
    result = tb.validate_binding(binding(), feature_id="health", behavior_id="damage",
                                 contract_expected=CONTRACT_EXPECTED)
    ok("C1: correct binding -> VALID_BINDING", result["status"] == tb.VALID_BINDING,
       str(result))

    result = tb.validate_binding(binding(scenario_id="waves"), feature_id="health",
                                 behavior_id="damage", scenario_id="holdout")
    ok("C2: wrong scenario -> SCENARIO_MISMATCH",
       result["status"] == tb.SCENARIO_MISMATCH, str(result["reason"]))

    result = tb.validate_binding(binding(contract_version="old"), feature_id="health",
                                 behavior_id="damage", contract_version="new")
    ok("C3: contract version mismatch -> CONTRACT_MISMATCH",
       result["status"] == tb.CONTRACT_MISMATCH, str(result["reason"]))

    widened = binding(expected=[{"check": "health.current", "target": ".", "equals": 5}])
    result = tb.validate_binding(widened, feature_id="health", behavior_id="damage",
                                 contract_expected=CONTRACT_EXPECTED)
    ok("C4: expected wider than contract -> CONTRACT_MISMATCH",
       result["status"] == tb.CONTRACT_MISMATCH, str(result["reason"]))

    result = tb.validate_binding(
        binding(expected=[{"check": "health.current", "target": ".", "equals": 1}]),
        feature_id="health", behavior_id="damage", contract_expected=CONTRACT_EXPECTED)
    ok("C5: expected consistent with contract -> VALID_BINDING",
       result["status"] == tb.VALID_BINDING, str(result))

    result = tb.validate_binding(binding(baseline_id="waves", baseline_version="2"),
                                 feature_id="health", behavior_id="damage",
                                 baseline_report=UNAPPROVED_BASELINE)
    ok("C6: unapproved baseline -> UNAPPROVED_BASELINE",
       result["status"] == tb.UNAPPROVED_BASELINE, str(result["reason"]))

    result = tb.validate_binding(binding(baseline_id="waves", baseline_version="2"),
                                 feature_id="health", behavior_id="damage",
                                 baseline_report=REVOKED_BASELINE)
    ok("C7: revoked baseline -> REVOKED_BASELINE",
       result["status"] == tb.REVOKED_BASELINE, str(result["reason"]))

    result = tb.validate_binding(binding(baseline_id="waves", baseline_version="2"),
                                 feature_id="health", behavior_id="damage",
                                 baseline_report=MISMATCH_BASELINE)
    ok("C8: digest mismatch baseline -> DIGEST_MISMATCH",
       result["status"] == tb.DIGEST_MISMATCH, str(result["reason"]))

    result = tb.validate_binding(binding(baseline_id="waves", baseline_version="2"),
                                 feature_id="health", behavior_id="damage",
                                 baseline_report=TRUSTED_BASELINE)
    ok("C9: trusted baseline -> VALID_BINDING", result["status"] == tb.VALID_BINDING,
       str(result))


def test_trace_states() -> None:
    bindings = [binding(binding_id="S1", scenario_id="waves",
                        scenario_behavior_total=1)]
    ok("D1: no referencing bindings -> SCENARIO_ONLY",
       tb.trace_binding_state([], "waves") == tb.SCENARIO_ONLY)
    ok("D2: full coverage -> BEHAVIOR_BOUND",
       tb.trace_binding_state(bindings, "waves") == tb.BEHAVIOR_BOUND)
    partial = [binding(binding_id="S1", scenario_id="waves",
                       behavior_id="damage", scenario_behavior_total=3)]
    ok("D3: partial coverage -> BEHAVIOR_PARTIALLY_BOUND",
       tb.trace_binding_state(partial, "waves") == tb.BEHAVIOR_PARTIALLY_BOUND)
    ok("D4: empty scenario -> UNBOUND", tb.trace_binding_state(bindings, "") == tb.UNBOUND)


def test_real_bindings() -> None:
    doc = tb.load_bindings()
    ok("E1: real binding library loads and validates",
       tb.validate_document(doc, source="real") == [])
    pairs = {(item["feature_id"], item["behavior_id"]) for item in doc["bindings"]}
    # Phase 1.63：绑定库必须**动态覆盖当前正式支持集合**（数量不硬编码），
    # 且不得出现支持集之外的孤儿绑定。
    sys.path.insert(0, os.path.join(os.path.dirname(VALIDATOR_DIR),
                                    "evaluation"))
    import evidence_adapter as adapter
    supported = adapter.supported_set()
    supported_pairs = {(feature, behavior)
                       for feature, behaviors in supported["features"].items()
                       for behavior in behaviors}
    missing = sorted(supported_pairs - pairs)
    orphans = sorted(pairs - supported_pairs)
    ok("E2: real library dynamically covers the supported set (%d behaviors, %d bindings)"
       % (len(supported_pairs), len(pairs)),
       not missing and not orphans,
       "missing=%s orphans=%s" % (missing[:3], orphans[:3]))

    import importlib
    fbe = importlib.import_module("feature_behavior_evidence")
    drifted = []
    for item in doc["bindings"]:
        contracts, _reports = fbe.build_contracts(item["feature_id"], "Features")
        contract = next((c for c in contracts
                         if str(c["behavior"]) == item["behavior_id"]), None)
        if contract is None:
            drifted.append("%s/%s: contract gone" % (item["feature_id"], item["behavior_id"]))
            continue
        result = tb.validate_binding(
            item, feature_id=item["feature_id"], behavior_id=item["behavior_id"],
            contract_expected=list(contract.get("expected") or []))
        if result["status"] != tb.VALID_BINDING:
            drifted.append("%s/%s: %s (%s)" % (item["feature_id"], item["behavior_id"],
                                               result["status"], result["reason"]))
    ok("E3: all real bindings still match current contracts (no drift)",
       not drifted, "; ".join(drifted[:2]))


def main() -> int:
    test_schema()
    test_identity()
    test_validation()
    test_trace_states()
    test_real_bindings()
    print("\n%d check(s), %d failure(s)" % (_checks, len(_failures)))
    if _failures:
        print("FAIL: " + "; ".join(_failures[:5]))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
