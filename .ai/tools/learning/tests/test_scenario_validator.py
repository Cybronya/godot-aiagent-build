#!/usr/bin/env python3
"""Phase 1.66：Scenario Validator 攻击测试。

真实契约/源码 + 临时知识库；覆盖伪造引用、撤销、过期、路径越界、依赖缺失等。
"""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LEARNING = os.path.dirname(HERE)
sys.path[:0] = [LEARNING, os.path.join(os.path.dirname(LEARNING), "scene_composer")]

import knowledge_v2  # noqa: E402
import scenario_generator as gen  # noqa: E402
import scenario_validate as validate  # noqa: E402

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
    root = tempfile.mkdtemp(prefix="p166_validation_")
    TMP.append(root)
    knowledge_v2.BASE = root
    knowledge_v2.RECORDS = os.path.join(root, "records")
    knowledge_v2.CANDIDATES = os.path.join(root, "candidates")
    knowledge_v2.CONFLICTS = os.path.join(root, "conflicts")
    for path in (knowledge_v2.RECORDS, knowledge_v2.CANDIDATES, knowledge_v2.CONFLICTS):
        os.makedirs(path, exist_ok=True)


def store(record: dict, status: str = "APPROVED") -> dict:
    record = copy.deepcopy(record)
    record["verification_status"] = status
    record["lifecycle_events"] = [{"at": record["created_at"], "event": "CREATE"}]
    path = os.path.join(knowledge_v2.RECORDS if status == "APPROVED" else knowledge_v2.CANDIDATES,
                        "%s.json" % record["knowledge_id"])
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2, sort_keys=True)
    return record


def main() -> int:
    real = [record for record in knowledge_v2.all_records()
            if record["feature_id"] == "trigger_switch" and record["key"] == "guards"
            and record["verification_status"] == "APPROVED"][0]
    base_scenario = gen.build(["trigger_switch/latch_once"])["scenarios"][0]

    isolate()
    stored = store(real)
    scenario = copy.deepcopy(base_scenario)
    scenario["knowledge_refs"] = [stored["knowledge_id"]]

    ok("V1: baseline scenario is VALID", validate.validate(scenario)["status"] == "VALID",
       validate.validate(scenario)["status"])

    forged = copy.deepcopy(scenario)
    forged["knowledge_refs"] = ["k-0000000000000000"]
    report = validate.validate(forged)
    ok("V2: forged knowledge id rejected", report["status"] == "INVALID",
       report["status"])

    wrong_contract = copy.deepcopy(scenario)
    wrong_contract["contract_version"] = "deadbeefcafe"
    ok("V3: wrong contract version is CONTRACT_MISMATCH",
       validate.validate(wrong_contract)["status"] == "CONTRACT_MISMATCH")

    escape = copy.deepcopy(scenario)
    escape["scene"] = "res://Features/../Features/trigger_switch/TriggerSwitch.tscn"
    ok("V4: scene path escape rejected",
       validate.validate(escape)["status"] in ("INVALID", "CONTRACT_MISMATCH"))

    empty = copy.deepcopy(scenario)
    empty["actions"] = []
    ok("V5: empty actions rejected", validate.validate(empty)["status"] == "INVALID")

    no_expected = copy.deepcopy(scenario)
    no_expected["expected_observations"] = []
    ok("V6: empty expectation rejected", validate.validate(no_expected)["status"] == "INVALID")

    dependency = copy.deepcopy(scenario)
    dependency["scenario_type"] = "DEPENDENCY_PRECONDITION"
    dependency["dependency_refs"] = []
    report = validate.validate(dependency)
    ok("V7: dependency scenario without edge refs is INCOMPLETE",
       report["status"] == "INCOMPLETE", report["status"])

    bad_edge = copy.deepcopy(base_scenario)
    bad_edge["dependency_refs"] = ["dep-9999"]
    bad_edge["scenario_type"] = "DEPENDENCY_PRECONDITION"
    bad_edge["knowledge_refs"] = [stored["knowledge_id"]]
    ok("V8: unknown dependency edge rejected",
       validate.validate(bad_edge)["status"] == "INVALID")

    stale_source = copy.deepcopy(stored)
    stale_source["knowledge_id"] = "k-source-stale-001"
    stale_source["source_references"] = [dict(stale_source["source_references"][0],
                                              digest="0" * 64)]
    store(stale_source)
    stale_scenario = copy.deepcopy(scenario)
    stale_scenario["knowledge_refs"] = [stale_source["knowledge_id"]]
    ok("V9: source digest mismatch is SOURCE_STALE",
       validate.validate(stale_scenario)["status"] == "SOURCE_STALE")

    stale_knowledge = copy.deepcopy(stored)
    stale_knowledge["knowledge_id"] = "k-contract-stale-001"
    stale_knowledge["contract_version"] = "000000000000"
    store(stale_knowledge)
    stale_contract_scenario = copy.deepcopy(scenario)
    stale_contract_scenario["knowledge_refs"] = [stale_knowledge["knowledge_id"]]
    ok("V10: stale knowledge contract version is KNOWLEDGE_STALE",
       validate.validate(stale_contract_scenario)["status"] == "KNOWLEDGE_STALE")

    revoked = copy.deepcopy(stored)
    revoked["knowledge_id"] = "k-revoked-001"
    revoked["verification_status"] = "REVOKED"
    revoked["lifecycle_events"].append({"at": revoked["created_at"], "event": "REVOKE"})
    with open(os.path.join(knowledge_v2.RECORDS, "k-revoked-001.json"), "w",
              encoding="utf-8") as handle:
        json.dump(revoked, handle, ensure_ascii=False)
    revoked_scenario = copy.deepcopy(scenario)
    revoked_scenario["knowledge_refs"] = ["k-revoked-001"]
    ok("V11: revoked knowledge rejected",
       validate.validate(revoked_scenario)["status"] == "INVALID")

    conflicting = copy.deepcopy(stored)
    conflicting["knowledge_id"] = "k-conflict-001"
    conflicting["content"] = {"conditions": [{"condition": "if false:", "file": "x", "line": 1}]}
    conflicting["content_digest"] = knowledge_v2._digest(conflicting["content"])
    store(conflicting)
    other = copy.deepcopy(stored)
    other["knowledge_id"] = "k-conflict-002"
    other["content"] = {"conditions": [{"condition": "if other:", "file": "x", "line": 1}]}
    knowledge_v2.add_candidate(other)
    conflict_scenario = copy.deepcopy(scenario)
    conflict_scenario["knowledge_refs"] = ["k-conflict-001"]
    ok("V12: open conflict blocks the scenario",
       validate.validate(conflict_scenario)["status"] in ("KNOWLEDGE_STALE", "INVALID"))

    no_source = copy.deepcopy(stored)
    no_source["knowledge_id"] = "k-nosource-001"
    no_source["source_references"] = [{"kind": "CONTRACT_REFERENCE",
                                       "reference": "Features/trigger_switch/template.yaml"}]
    store(no_source)
    nosource_scenario = copy.deepcopy(scenario)
    nosource_scenario["knowledge_refs"] = [no_source["knowledge_id"]]
    ok("V13: scenario without SOURCE_REFERENCE is INCOMPLETE",
       validate.validate(nosource_scenario)["status"] == "INCOMPLETE")

    outside = copy.deepcopy(stored)
    outside["knowledge_id"] = "k-outside-001"
    outside["source_references"] = [{"kind": "SOURCE_REFERENCE",
                                     "reference": "README.md:1"}]
    store(outside)
    outside_scenario = copy.deepcopy(scenario)
    outside_scenario["knowledge_refs"] = [outside["knowledge_id"]]
    ok("V14: source reference outside Features/ rejected",
       validate.validate(outside_scenario)["status"] in ("INVALID", "SOURCE_STALE"))

    tampered = copy.deepcopy(base_scenario)
    tampered["actions"][0]["type"] = "no.such.action"
    ok("V15: unknown action type rejected",
       validate.validate(tampered)["status"] == "INVALID")

    too_long = copy.deepcopy(base_scenario)
    too_long["window_frames"] = 100000
    ok("V16: frame budget overflow rejected", validate.validate(too_long)["status"] == "INVALID")

    no_cleanup = copy.deepcopy(base_scenario)
    no_cleanup["cleanup"] = []
    ok("V17: missing cleanup rejected", validate.validate(no_cleanup)["status"] == "INVALID")

    no_refs = copy.deepcopy(base_scenario)
    no_refs["knowledge_refs"] = []
    ok("V18: scenario without knowledge refs is INCOMPLETE",
       validate.validate(no_refs)["status"] == "INCOMPLETE")

    print("\n===== test_scenario_validator: %d checks, %d failures =====" % (checks, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
