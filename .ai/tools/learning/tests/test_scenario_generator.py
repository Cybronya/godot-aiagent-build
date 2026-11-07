#!/usr/bin/env python3
"""Phase 1.66：Knowledge-Driven Scenario Generator 测试。

只读真实 Knowledge Store / 契约；不写执行产物。
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LEARNING = os.path.dirname(HERE)
sys.path[:0] = [LEARNING, os.path.join(os.path.dirname(LEARNING), "scene_composer")]

import knowledge_v2  # noqa: E402
import scenario_generator as gen  # noqa: E402

checks = 0
failures = 0
PILOT = ["openable_door/open", "i_frames/iframes_expire_and_damage_resumes",
         "save_game/save_slot_persists_world_state", "trigger_switch/latch_once",
         "health/damage"]


def ok(name: str, condition: bool, detail: str = "") -> None:
    global checks, failures
    checks += 1
    if condition:
        print("PASS: %s" % name)
    else:
        failures += 1
        print("FAIL: %s %s" % (name, detail))


def main() -> int:
    document = gen.build(PILOT)
    scenarios = document["scenarios"]
    ok("G1: scenarios generated for every pilot behavior",
       {item["behavior"] for item in scenarios} == set(PILOT),
       str({item["behavior"] for item in scenarios}))
    ok("G2: at least five scenarios", len(scenarios) >= 5, str(len(scenarios)))
    ok("G3: scenario ids are stable sha256 prefixes",
       all(item["scenario_id"].startswith("s-") and len(item["scenario_id"]) == 18
           for item in scenarios))
    ok("G4: ids unique", len({item["scenario_id"] for item in scenarios}) == len(scenarios))
    ok("G5: every scenario declares knowledge refs",
       all(item["knowledge_refs"] for item in scenarios))
    ok("G6: every knowledge ref is APPROVED",
       all(knowledge_v2.get(ref)["verification_status"] == "APPROVED"
           for item in scenarios for ref in item["knowledge_refs"]))
    ok("G7: every scenario has executable actions",
       all(item["actions"] for item in scenarios))
    ok("G8: every scenario has verifiable expectations",
       all(item["expected_observations"] for item in scenarios))
    ok("G9: every expectation has a check name",
       all(check.get("check") for item in scenarios
           for check in item["expected_observations"]))
    ok("G10: every scenario references a scene inside Features/",
       all(item["scene"].startswith("res://Features/") for item in scenarios))
    ok("G11: derivation explains the knowledge fact",
       all(len(item["derivation"]) > 40 for item in scenarios))
    ok("G12: scenarios are marked NOT_EXECUTED", 
       all(item["execution_status"] == "NOT_EXECUTED" for item in scenarios))
    ok("G13: contract version recorded from real contract",
       all(len(item["contract_version"]) == 12 for item in scenarios))
    # 规则目录不含 hardcoded feature/behavior 列表（协议动词如 health.take_damage 不算）
    source = open(os.path.join(LEARNING, "scenario_generator.py"), encoding="utf-8").read()
    quoted = ['"%s/' % name.split("/")[0] for name in PILOT]
    ok("G14: generator source contains no hardcoded feature/behavior pair",
       not any(token in source for token in quoted), str(quoted))
    # 未知 Behavior 不猜
    missing = gen.generate_behavior("openable_door", "not_a_behavior")
    ok("G15: unknown behavior yields CONTRACT_NOT_FOUND",
       missing["skipped"] == "CONTRACT_NOT_FOUND" and not missing["scenarios"])
    # 已存在契约重复动作的 Behavior 不应生成幂等场景（去重）
    repeated = [item for item in scenarios if item["rule_id"] == "idempotent_repeat"]
    ok("G16: idempotent rule only where a guard exists",
       all("== value" in item["derivation"] for item in repeated))
    print("\n===== test_scenario_generator: %d checks, %d failures =====" % (checks, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
