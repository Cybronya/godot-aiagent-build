#!/usr/bin/env python3
"""Phase 1.68.2：按键官方契约判定器测试（不启动 Godot）。"""

from __future__ import annotations

import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VALIDATOR = os.path.dirname(HERE)
TOOLS = os.path.dirname(VALIDATOR)
sys.path[:0] = [VALIDATOR, os.path.join(TOOLS, "scene_composer"), TOOLS]

import check_behavior_evidence as cbe  # noqa: E402
import feature_behavior_evidence as fbe  # noqa: E402

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


def expected_checks() -> list[dict]:
    return [
        {"check": "health.current", "target": "Player/Health", "equals": 4},
        {"check": "signal", "target": "Saver", "entry": "save", "count": 1},
    ]


def actual_checks() -> list[dict]:
    return [
        {"check": "health.current", "target": "Player/Health", "observed": 4},
        {"check": "signal", "target": "Saver", "entry": "save",
         "observed": 1, "observed_args": []},
    ]


def record(actual: list, status: str = "PASS") -> dict:
    return {"evidence": fbe.EVIDENCE_BEHAVIOR, "action_executed": True, "replay_count": 2,
            "replay_consistent": True, "status": status, "actual": actual}


def main() -> int:
    contract = {"expected": expected_checks()}
    base = record(actual_checks())

    verdict = cbe.judge_record_keyed(base, contract)
    ok("K1: keyed normal PASS", verdict["status"] == cbe.STATUS_PASS, str(verdict))
    ok("K2: every contract check has a verdict",
       len(verdict["checks"]) == 2 and
       all(item["verdict"] == cbe.STATUS_PASS for item in verdict["checks"]))
    ok("K3: extra observations are empty", verdict["extra_keys"] == [])

    shuffled = record(list(reversed(actual_checks())))
    ok("K4: keyed order does not matter",
       cbe.judge_record_keyed(shuffled, contract)["status"] == cbe.STATUS_PASS)

    extra = copy.deepcopy(base)
    extra["actual"].append({"check": "signal", "target": "Other", "entry": "x",
                            "observed": 9})
    extra_verdict = cbe.judge_record_keyed(extra, contract)
    ok("K5: extra observation does not fail the contract",
       extra_verdict["status"] == cbe.STATUS_PASS and extra_verdict["extra_keys"])

    missing = record([actual_checks()[0]])
    missing_verdict = cbe.judge_record_keyed(missing, contract)
    ok("K6: missing check is INCOMPLETE",
       missing_verdict["status"] == cbe.STATUS_INCOMPLETE and
       missing_verdict["reason"] == "observation_incomplete")

    duplicate = record(actual_checks() + [dict(actual_checks()[0])])
    duplicate_verdict = cbe.judge_record_keyed(duplicate, contract)
    ok("K7: duplicate actual key is INCOMPLETE",
       duplicate_verdict["status"] == cbe.STATUS_INCOMPLETE and
       duplicate_verdict["reason"] == "duplicate_observation_key")
    ok("K8: duplicate key is reported, not silently deduplicated",
       duplicate_verdict["duplicate_actual_keys"])

    duplicate_contract = {"expected": expected_checks() + [dict(expected_checks()[0])]}
    contract_verdict = cbe.judge_record_keyed(base, duplicate_contract)
    ok("K9: duplicate contract key is INCOMPLETE",
       contract_verdict["status"] == cbe.STATUS_INCOMPLETE and
       contract_verdict["reason"] == "ambiguous_contract_key")

    wrong = record([{"check": "health.current", "target": "Player/Health",
                     "observed": 3}, actual_checks()[1]])
    wrong_verdict = cbe.judge_record_keyed(wrong, contract)
    ok("K10: value mismatch is FAIL",
       wrong_verdict["status"] == cbe.STATUS_FAIL and
       wrong_verdict["reason"] == "contract_violation")

    invalid = record([actual_checks()[0], "not-an-object"])
    invalid_verdict = cbe.judge_record_keyed(invalid, contract)
    ok("K11: malformed observation is INCOMPLETE",
       invalid_verdict["status"] == cbe.STATUS_INCOMPLETE and
       invalid_verdict["reason"] == "invalid_observation")

    empty_verdict = cbe.judge_record_keyed(record([]), contract)
    ok("K12: empty observation is INCOMPLETE",
       empty_verdict["status"] == cbe.STATUS_INCOMPLETE)

    # 旧判定器保持原语义：多一个检查项仍按条数判定为 INCOMPLETE。
    old = cbe.judge_record(base, contract)
    old_extra = cbe.judge_record(extra, contract)
    ok("K13: legacy judge still PASSes its exact shape",
       old["status"] == cbe.STATUS_PASS, str(old))
    ok("K14: legacy judge is not replaced by keyed semantics",
       old_extra["status"] == cbe.STATUS_INCOMPLETE and
       old_extra["reason"] == "observation_count_mismatch", str(old_extra))

    print("\n===== test_keyed_judge: %d checks, %d failures =====" % (checks, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
