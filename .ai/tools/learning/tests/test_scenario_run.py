#!/usr/bin/env python3
"""Phase 1.66：Execution Planner 测试（不启动 Godot）。

验证指纹来自真实环境、Run ID 唯一、隔离路径、非法场景被拒绝。
"""

from __future__ import annotations

import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LEARNING = os.path.dirname(HERE)
TOOLS = os.path.dirname(LEARNING)
sys.path[:0] = [LEARNING, os.path.join(TOOLS, "scene_composer"),
                os.path.join(TOOLS, "validator", "execution")]

import scenario_generator as gen  # noqa: E402
import scenario_run as run  # noqa: E402

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


def main() -> int:
    scenario = gen.build(["openable_door/open"])["scenarios"][0]
    scenario["validation_status"] = "VALID"
    plan = run.execution_plan(scenario, label="TEST")

    ok("R1: valid scenario yields READY plan", plan["status"] == "READY",
       str(plan["blocked_reasons"]))
    ok("R2: plan carries a unique run id",
       isinstance(plan["run_id"], str) and len(plan["run_id"]) > 20)
    ok("R3: four fingerprints are present and non-empty",
       all(len(plan[key]) == 64 for key in
           ("environment_fingerprint", "source_fingerprint", "collector_fingerprint",
            "execution_config_fingerprint")))
    ok("R4: output root is under the p166 isolation dir",
       plan["output_root"].startswith(".ai/tmp/p166/runs/"))
    ok("R5: user dir tag is scenario-scoped",
       plan["isolation"]["user_dir_tag"] == "p166-%s" % scenario["scenario_id"])
    ok("R6: plan records timeout and cleanup policy",
       plan["timeout_policy"]["replay"] == 2 and plan["cleanup_policy"]["keep_artifacts"])
    ok("R7: prerequisites include validator + godot + scene",
       {item["name"] for item in plan["prerequisites"]} == {"validator", "godot", "scene"})

    second = run.execution_plan(scenario, label="TEST")
    ok("R8: two plans never share a run id", second["run_id"] != plan["run_id"])

    invalid = copy.deepcopy(scenario)
    invalid["actions"] = []
    blocked = run.execution_plan(invalid, label="TEST")
    ok("R9: invalid scenario is BLOCKED", blocked["status"] == "BLOCKED")
    record = run.run_scenario(invalid, label="TEST-REFUSE")
    ok("R10: blocked plan never executes (status ENVIRONMENT_BLOCKED)",
       record["execution_status"] == "ENVIRONMENT_BLOCKED")
    ok("R11: blocked execution records no evidence",
       record["evidence_status"] == "NOT_COLLECTED" and not record["bundle_path"])
    ok("R12: blocked execution keeps validator status visible",
       record["validator_status"] == "VALID" and record["detail"])

    print("\n===== test_scenario_run: %d checks, %d failures =====" % (checks, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
