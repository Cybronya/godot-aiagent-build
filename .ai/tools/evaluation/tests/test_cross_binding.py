#!/usr/bin/env python3
"""Cross-Binding Validation 集成测试（Phase 1.60，任务书 §8.4）。

被测对象：`evidence_adapter.evaluate_task` 的绑定门禁 +
`baseline_report` 的使用时摘要复核 + `binding_reconciliation`。

证据夹具：`evidence_fixtures`（真实契约形态 + 签名 bundle，与 1.58 同源）。

覆盖矩阵：
    CB1 正确 Binding + 正确证据（expected_source=behavior_contract）-> VERIFIED_PASS
        且期望确实取自绑定
    CB2 缺失 Binding（声明 expected_source）-> INCOMPLETE binding_missing
    CB3 过期 Binding（contract_version 失配）-> NOT_EVALUATED binding_contract_mismatch
    CB4 绑定 Baseline 未审批 -> NOT_EVALUATED baseline_unapproved
    CB5 绑定 Baseline 审批后内容被改 -> NOT_EVALUATED baseline_digest_mismatch
    CB6 绑定 Scenario 与任务场景不一致 -> NOT_EVALUATED binding_scenario_mismatch
    CB7 场景级 Trace 被错误用于逐 Behavior 评估 -> INCOMPLETE binding_missing（不升级）
    CB8 未声明 expected_source 的任务保持 1.58 语义（场景级 trace 仍 NOT_APPLICABLE，
        评估不因绑定缺失而降级）—— Phase 1.58 回归守卫
    CB9 跨 Feature 证据误用 -> INCOMPLETE no_evidence（不因绑定存在而放行）
    CB10 绑定覆盖对账（动态支持集 x 绑定库）

用法：python .ai/tools/evaluation/tests/test_cross_binding.py
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.dirname(_HERE)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(EVAL_DIR)))
for _path in (_HERE, EVAL_DIR, os.path.join(PROJECT_ROOT, ".ai", "tools", "validator")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import evidence_adapter as adapter                               # noqa: E402
import evidence_fixtures as fixtures                             # noqa: E402
import baseline_lifecycle as bl                                  # noqa: E402
import trace_bindings as tb                                      # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_checks = 0
_failures: list = []
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


PAIRS = fixtures.feature_pairs(["collect_pickup", "health"])
SUPPORTED = adapter.supported_set()


def make_verified() -> dict:
    root = new_dir("p160-cb-")
    evidence_dir, artifacts = fixtures.make_evidence_dir(root, PAIRS)
    return adapter.load_verified(evidence_dir=evidence_dir,
                                 features=fixtures.feature_pairs.__self__ if False else
                                 ["collect_pickup", "health"],
                                 artifact_roots=[artifacts]), root


def binding_doc(items: list) -> dict:
    return {"schema": tb.SCHEMA, "schema_version": tb.SCHEMA_VERSION, "bindings": items}


def real_binding(feature: str, behavior: str) -> dict:
    doc = tb.load_bindings()
    item = tb.get_binding(doc, feature, behavior)
    assert item is not None, "real binding %s/%s missing" % (feature, behavior)
    return copy.deepcopy(item)


def write_baseline(directory: str, name: str, document: dict, registry: str) -> str:
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle)
    return path


def sample_baseline(scenario: str = "waves_like") -> dict:
    return {
        "document": "orchestration_trace_baseline",
        "baseline_schema_version": 1, "baseline_version": 1,
        "scenario_id": scenario,
        "scenario_description": "cross-binding test baseline",
        "approved_behavior_version": "1",
        "trace_schema_version": 1,
        "comparison_policy": {"version": 1,
                              "ignored_event_fields": ["run_id", "timestamp_ms"],
                              "data": {"mode": "strict", "ignored_fields": [],
                                       "numeric_tolerance": 1e-09}},
        "events": [{"event_type": "orchestration_started", "sequence": 0,
                    "timestamp_ms": 0, "run_id": "run-cb", "schema_version": 1,
                    "source": "orchestrator", "entity_id": None,
                    "instance_name": None, "reason": "waves", "stage_id": None,
                    "stage_index": None, "data": {"mode": "waves", "stage_count": 0}}],
        "expected_final_state": {"final_state": "completed"},
        "coverage": {"chain": "started"},
        "approval": {"status": "approved", "approver": "tester",
                     "approved_at": "2026-11-03T00:00:00Z",
                     "candidate_fingerprint": "1" * 16},
    }


def test_cross_binding() -> None:
    # 持有真实注册表的备份：绑定级 baseline 测试使用临时注册表
    real_registry = bl.REGISTRY_PATH
    tmp_registry = os.path.join(new_dir("p160-reg-"), "registry.json")
    bl.REGISTRY_PATH = tmp_registry

    verified, root = make_verified()

    # ---- CB1 正确绑定 -> VERIFIED_PASS，期望取自绑定
    task = {"id": "CB1", "feature": "health", "behavior": "damage",
            "expected_source": "behavior_contract"}
    record = adapter.evaluate_task(task, verified, SUPPORTED,
                                   bindings=binding_doc([real_binding("health", "damage")]))
    first = record["behaviors"][0]
    ok("CB1: valid binding + valid evidence -> VERIFIED_PASS",
       record["evaluation_status"] == adapter.VERIFIED_PASS,
       json.dumps(record, ensure_ascii=False)[:300])
    ok("CB1: binding_status reported and expectation came from binding",
       first.get("binding_status") == tb.VALID_BINDING
       and first.get("expected_source") == "behavior_contract", str(first)[:200])
    ok("CB1: binding expectation equals contract expectation (not widened)",
       first["expectation"]["state"] == "MET", str(first.get("expectation", {}))[:200])

    # ---- CB2 缺失绑定 -> INCOMPLETE
    task = {"id": "CB2", "feature": "health", "behavior": "damage",
            "expected_source": "behavior_contract"}
    record = adapter.evaluate_task(task, verified, SUPPORTED,
                                   bindings=binding_doc([]))
    ok("CB2: missing binding -> INCOMPLETE binding_missing",
       record["evaluation_status"] == adapter.INCOMPLETE
       and record["behaviors"][0]["reason"] == "binding_missing",
       json.dumps(record["behaviors"][0], ensure_ascii=False)[:200])

    # ---- CB3 过期绑定（contract_version 失配）-> NOT_EVALUATED
    stale = real_binding("health", "damage")
    stale["contract_version"] = "outdated000"
    task = {"id": "CB3", "feature": "health", "behavior": "damage",
            "expected_source": "behavior_contract", "contract_version": "current"}
    record = adapter.evaluate_task(task, verified, SUPPORTED,
                                   bindings=binding_doc([stale]))
    ok("CB3: stale binding -> NOT_EVALUATED binding_contract_mismatch",
       record["evaluation_status"] == adapter.NOT_EVALUATED
       and record["behaviors"][0]["reason"] == "binding_contract_mismatch",
       json.dumps(record["behaviors"][0], ensure_ascii=False)[:200])

    # ---- CB4 绑定 Baseline 未审批 -> NOT_EVALUATED
    bdir = new_dir("p160-bl-")
    unapproved_path = write_baseline(bdir, "unapproved.json", sample_baseline(),
                                     tmp_registry)
    with open(unapproved_path, "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    doc["approval"]["status"] = "pending"
    with open(unapproved_path, "w", encoding="utf-8") as handle:
        json.dump(doc, handle)
    with_baseline = real_binding("health", "damage")
    with_baseline["baseline_id"] = "unapproved"
    with_baseline["baseline_path"] = unapproved_path
    task = {"id": "CB4", "feature": "health", "behavior": "damage",
            "expected_source": "behavior_contract"}
    record = adapter.evaluate_task(task, verified, SUPPORTED,
                                   bindings=binding_doc([with_baseline]))
    ok("CB4: unapproved bound baseline -> NOT_EVALUATED baseline_unapproved",
       record["evaluation_status"] == adapter.NOT_EVALUATED
       and record["behaviors"][0]["reason"] == "baseline_unapproved",
       json.dumps(record["behaviors"][0], ensure_ascii=False)[:200])

    # ---- CB5 Baseline 审批后内容被改 -> DIGEST_MISMATCH 门禁
    approved_path = os.path.join(bdir, "approved.json")
    document = sample_baseline("approved_case")
    bl.register("approved_case", 1, bl.APPROVED,
                digest=bl.content_digest(document)["digest"],
                approver="tester", approved_at="2026-11-03T00:00:00Z",
                basis="test", registry_path=tmp_registry)
    with open(approved_path, "w", encoding="utf-8") as handle:
        json.dump(document, handle)
    tampered = copy.deepcopy(document)
    tampered["events"][0]["data"]["mode"] = "boss"
    tampered_path = os.path.join(bdir, "tampered.json")
    with open(tampered_path, "w", encoding="utf-8") as handle:
        json.dump(tampered, handle)
    with_baseline = real_binding("health", "damage")
    with_baseline["baseline_id"] = "approved_case"
    with_baseline["baseline_path"] = tampered_path
    task = {"id": "CB5", "feature": "health", "behavior": "damage",
            "expected_source": "behavior_contract"}
    record = adapter.evaluate_task(task, verified, SUPPORTED,
                                   bindings=binding_doc([with_baseline]))
    ok("CB5: tampered bound baseline -> NOT_EVALUATED baseline_digest_mismatch",
       record["evaluation_status"] == adapter.NOT_EVALUATED
       and record["behaviors"][0]["reason"] == "baseline_digest_mismatch",
       json.dumps(record["behaviors"][0], ensure_ascii=False)[:200])

    # ---- CB6 场景不一致 -> NOT_EVALUATED
    mismatched = real_binding("health", "damage")
    mismatched["scenario_id"] = "holdout"
    task = {"id": "CB6", "feature": "health", "behavior": "damage",
            "expected_source": "behavior_contract",
            "trace": {"scenario": "waves"}}
    record = adapter.evaluate_task(task, verified, SUPPORTED,
                                   bindings=binding_doc([mismatched]))
    ok("CB6: scenario mismatch -> NOT_EVALUATED binding_scenario_mismatch",
       record["evaluation_status"] == adapter.NOT_EVALUATED
       and record["behaviors"][0]["reason"] == "binding_scenario_mismatch",
       json.dumps(record["behaviors"][0], ensure_ascii=False)[:200])

    # ---- CB7 场景级 Trace 被错误用于逐 Behavior 评估 -> 不升级
    task = {"id": "CB7", "feature": "health", "behavior": "damage",
            "expected_source": "golden_trace", "trace": {"scenario": "waves"}}
    record = adapter.evaluate_task(task, verified, SUPPORTED, bindings=binding_doc([]))
    ok("CB7: scenario trace cannot back per-behavior expectation -> INCOMPLETE",
       record["evaluation_status"] == adapter.INCOMPLETE
       and record["behaviors"][0]["reason"] == "binding_missing",
       json.dumps(record["behaviors"][0], ensure_ascii=False)[:200])

    # ---- CB8 Phase 1.58 回归守卫：未声明来源的任务语义不变
    task = {"id": "CB8", "feature": "health", "behavior": "damage",
            "trace": {"scenario": "waves"},
            "expect": [{"check": "health.current", "target": ".", "equals": 1},
                       {"check": "signal", "entry": "health.health_changed",
                        "target": ".", "count": 1}]}
    record = adapter.evaluate_task(task, verified, SUPPORTED, bindings=binding_doc([]))
    ok("CB8: task without expected_source keeps Phase 1.58 semantics (VERIFIED_PASS)",
       record["evaluation_status"] == adapter.VERIFIED_PASS,
       json.dumps(record, ensure_ascii=False)[:200])
    ok("CB8: scenario-level trace stays NOT_APPLICABLE (no auto-upgrade)",
       (record.get("golden_trace") or {}) == {} or
       record["behaviors"][0].get("binding_status") is None, "")

    # ---- CB9 跨 Feature 证据误用
    task = {"id": "CB9", "feature": "health", "behavior": "damage",
            "expected_source": "behavior_contract"}
    collect_only = {"validator": verified["validator"],
                    "behaviors": [item for item in verified["behaviors"]
                                  if item["feature"] == "collect_pickup"]}
    record = adapter.evaluate_task(task, collect_only, SUPPORTED,
                                   bindings=binding_doc([real_binding("health", "damage")]))
    ok("CB9: foreign-feature evidence -> INCOMPLETE no_evidence",
       record["behaviors"][0]["evaluation_status"] == adapter.INCOMPLETE
       and record["behaviors"][0]["reason"] == "no_evidence",
       json.dumps(record["behaviors"][0], ensure_ascii=False)[:150])

    # ---- CB10 绑定覆盖对账
    reconciliation = adapter.binding_reconciliation(
        SUPPORTED, tb.load_bindings(),
        scenarios=["waves", "holdout", "single_stage_boss", "multi_stage_boss"])
    ok("CB10: reconciliation is dynamic (supported from registry)",
       reconciliation["supported_behaviors"] > 0
       and reconciliation["supported_features"] > 0, str(reconciliation)[:150])
    # Phase 1.63：绑定库已覆盖整个动态支持集——断言结构一致性而非历史数量。
    ok("CB10: bindings cover the dynamic supported set consistently",
       reconciliation["bound_behaviors"] == reconciliation["supported_behaviors"]
       and reconciliation["unbound_behaviors"] == 0
       and reconciliation["approved_bindings"] ==
       reconciliation["supported_behaviors"], str(reconciliation)[:200])
    ok("CB10: orchestration scenario traces stay SCENARIO_ONLY",
       set(reconciliation["trace_binding_states"].values()) == {tb.SCENARIO_ONLY},
       str(reconciliation["trace_binding_states"]))

    bl.REGISTRY_PATH = real_registry


def main() -> int:
    test_cross_binding()
    cleanup()
    print("\n%d check(s), %d failure(s)" % (_checks, len(_failures)))
    if _failures:
        print("FAIL: " + "; ".join(_failures[:5]))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
