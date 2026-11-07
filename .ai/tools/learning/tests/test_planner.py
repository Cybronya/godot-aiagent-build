#!/usr/bin/env python3
"""Phase 1.65：Learning Planner 测试（缺口、优先级、阻塞、知识驱动变化）。"""

from __future__ import annotations

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LEARNING = os.path.dirname(HERE)
sys.path[:0] = [LEARNING]

import knowledge_v2  # noqa: E402
import paths  # noqa: E402
import planner  # noqa: E402

MATRIX = os.path.join(paths.ROOT, ".ai", "tmp", "p164", "batch1", "matrix_after",
                      "coverage_matrix.json")

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


def tasks_of(plan: dict, behavior: str) -> dict:
    return {task["task_type"]: task for task in plan["tasks"] if task["behavior"] == behavior}


def main() -> int:
    if not os.path.isfile(MATRIX):
        print("SKIP: matrix not found at %s" % MATRIX)
        return 0

    plan = planner.build_plan(matrix_path=MATRIX, label="test")
    ok("P1: plan documents its priority formula",
       "priority = 3*severity" in plan["formula"])
    ok("P2: every task has priority/rationale/cost/expected outputs",
       all({"priority", "rationale", "estimated_cost", "expected_outputs"} <= set(task)
           for task in plan["tasks"]))
    ok("P3: priority is reproducible from the documented terms",
       all(abs(task["priority"] - round(
           3 * planner.GAPS[task["gap"]][0]
           + paths.risk_of(task["feature_id"], task["behavior_id"]) / 2
           + _upstream(plan, task["behavior"])
           + (2 if _has_failure(task["behavior"]) else 0)
           - task["estimated_cost"], 1)) < 0.05 for task in plan["tasks"]),
       "priority mismatch")

    # 覆盖面：缺口全部来自真实数据
    behaviors = {"%s/%s" % (item["feature_id"], item["behavior_id"])
                 for item in paths.supported_behaviors()}
    ok("P4: tasks only cover the dynamic supported set",
       {task["behavior"] for task in plan["tasks"]} <= behaviors)
    ok("P5: behaviors without evidence get execution tasks",
       any(task["behavior"] == "patrol_movement/loop_patrol_cycles_waypoints"
           and task["task_type"] in ("EXECUTE_BEHAVIOR", "DESIGN_TEST_SCENARIO")
           for task in plan["tasks"]))
    ok("P6: behaviors with evidence do not get EXECUTE_BEHAVIOR for missing evidence",
       "EXECUTE_BEHAVIOR" not in tasks_of(plan, "openable_door/open"))

    # 知识入库后：同类任务被排除，且不再生成 KNOWLEDGE_INCOMPLETE
    ok("P7: approved knowledge removes completed tasks from the plan",
       plan["summary"]["excluded_completed"] > 0
       and any(item["behavior"] == "openable_door/open"
               for item in plan["excluded"]))
    ok("P8: behavior with approved knowledge has no UPDATE_KNOWLEDGE task",
       "UPDATE_KNOWLEDGE" not in tasks_of(plan, "openable_door/open"))

    # 知识驱动：引用必须指向已审批知识（真实库中没有待驱动任务时为 0，不算失败）
    driven = [task for task in plan["tasks"] if task["driven_by_knowledge"]]
    ok("P9: cited knowledge is always APPROVED",
       all((knowledge_v2.get(knowledge_id) or {}).get("verification_status") == "APPROVED"
           for task in driven for knowledge_id in task["driven_by_knowledge"]),
       str([(task["behavior"], task["task_type"]) for task in driven]))
    # 机制本身必须仍可被触发：P4 真实结果会让有场景证据的 Behavior 不再需要
    # DESIGN_TEST_SCENARIO，所以用「无执行结果」的输入重建计划（不改知识库），
    # 此时带守卫知识的 Behavior 必须产生引用该知识的任务。
    missing_results = os.path.join(paths.ROOT, ".ai", "tmp", "p166", "no_such_results.json")
    if os.path.isfile(missing_results):
        os.remove(missing_results)
    guarded_plan = planner.build_plan(matrix_path=MATRIX, label="test-driving",
                                      scenario_results_path=missing_results)
    guarded_driven = [task for task in guarded_plan["tasks"] if task["driven_by_knowledge"]]
    ok("P9b: the citation mechanism is exercised when design tasks exist",
       bool(guarded_driven) and all(
           (knowledge_v2.get(knowledge_id) or {}).get("verification_status") == "APPROVED"
           for task in guarded_driven for knowledge_id in task["driven_by_knowledge"]),
       str([(task["behavior"], task["task_type"]) for task in guarded_driven]))

    # 环境阻塞
    original = planner.environment_ready
    planner.environment_ready = lambda: (False, "godot missing (test)")
    try:
        blocked_plan = planner.build_plan(matrix_path=MATRIX, label="blocked")
    finally:
        planner.environment_ready = original
    ok("P10: missing environment blocks execution tasks explicitly",
       blocked_plan["summary"]["blocked"] > 0
       and all(task["blocking_conditions"] for task in blocked_plan["tasks"]
               if task["status"] == "BLOCKED"))

    # 无知识 vs 有知识：计划规模与任务集合确实变化
    original_records = knowledge_v2.all_records
    knowledge_v2.all_records = lambda: []
    try:
        empty_plan = planner.build_plan(matrix_path=MATRIX, label="no-knowledge")
    finally:
        knowledge_v2.all_records = original_records
    ok("P11: empty knowledge store produces more tasks than the populated one",
       empty_plan["summary"]["tasks"] > plan["summary"]["tasks"])
    ok("P12: empty knowledge store adds UPDATE_KNOWLEDGE for every behavior",
       empty_plan["summary"]["by_type"].get("UPDATE_KNOWLEDGE", 0)
       > plan["summary"]["by_type"].get("UPDATE_KNOWLEDGE", 0))

    # 缺 matrix 必须失败（不允许默认扫描）
    try:
        planner.build_plan(matrix_path="", label="bad")
        ok("P13: planner refuses to run without an explicit matrix", False)
    except SystemExit:
        ok("P13: planner refuses to run without an explicit matrix", True)

    # 冲突缺口：临时造一个 OPEN 冲突，计划里应出现 RESOLVE_KNOWLEDGE_CONFLICT
    original_conflicts = knowledge_v2.conflicts
    knowledge_v2.conflicts = lambda status="": [{
        "conflict_id": "c-test", "feature_id": "openable_door", "behavior_id": "open",
        "status": "OPEN"}] if status == "OPEN" else []
    try:
        conflict_plan = planner.build_plan(matrix_path=MATRIX, label="conflict")
    finally:
        knowledge_v2.conflicts = original_conflicts
    ok("P14: open conflict produces a conflict-resolution task",
       "RESOLVE_KNOWLEDGE_CONFLICT" in tasks_of(conflict_plan, "openable_door/open"))

    ok("P15: plan summary reports type distribution and behavior count",
       set(plan["summary"]["by_type"]) and plan["summary"]["behaviors_with_tasks"] > 0)
    print("\n===== test_planner: %d checks, %d failures =====" % (checks, failures))
    return 1 if failures else 0


def _upstream(plan: dict, behavior: str) -> int:
    import dependencies

    graph = dependencies.load() if os.path.isfile(dependencies.GRAPH_PATH) else {"edges": []}
    count = sum(1 for edge in graph["edges"] if edge["target_behavior"] == behavior)
    return min(count, 6)


def _has_failure(behavior: str) -> bool:
    feature_id, _, behavior_id = behavior.partition("/")
    return any(record["knowledge_type"] == "FAILURE_KNOWLEDGE"
               for record in knowledge_v2.all_records()
               if record["feature_id"] == feature_id and record["behavior_id"] == behavior_id)


if __name__ == "__main__":
    raise SystemExit(main())
