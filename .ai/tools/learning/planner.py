"""Learning Planner（Phase 1.65）。

从**真实数据**识别知识缺口并生成学习任务：不按「Knowledge 数量少」判断学习不足，
也不因为某个 Behavior 容易测就永远排在最前。

优先级公式（每一项都可解释，输出里逐项写出）：

    priority = 3*severity + risk/2 + upstream_impact + failure_bonus - cost

- `severity`：缺口严重度（1..3，见 GAPS）。
- `risk/2`：1.64 审计过的行为风险分（0..20）折半，避免长尾细节压过真实风险。
- `upstream_impact`：该 Behavior 的下游依赖数（被多少 Behavior 依赖），有上限。
- `failure_bonus`：有历史失败知识（FAILURE_KNOWLEDGE / failure_modes）时 +2。
- `cost`：估算成本（读代码 1、设计场景 2、真实执行 4…），**减**项，防止只挑最便宜的活。

缺口全部来自磁盘：分析文件、依赖图、矩阵、Knowledge Store、环境探测。
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import time

import dependencies
import knowledge_v2
import paths
import source_analysis

PLAN_PATH = os.path.join(paths.LEARNING_STATE, "learning_plan.json")
SCENARIO_RESULTS = os.path.join(paths.LEARNING_STATE, "scenario_results.json")
SCHEMA = "learning_plan"
SCHEMA_VERSION = 1

# 缺口 → (严重度, 任务类型, 成本)
GAPS = {
    "SOURCE_NOT_ANALYZED": (2, "ANALYZE_SOURCE", 1),
    "SOURCE_ENTRY_AMBIGUOUS": (2, "ANALYZE_SOURCE", 2),
    "SOURCE_NOT_FOUND": (3, "ANALYZE_SOURCE", 2),
    "DEPENDENCY_UNKNOWN": (2, "ANALYZE_DEPENDENCIES", 1),
    "CONTRACT_UNDERSTOOD_ONLY": (2, "ANALYZE_SOURCE", 1),
    "NO_RUNTIME_OBSERVATION": (3, "EXECUTE_BEHAVIOR", 4),
    "NO_TEST_SCENARIO": (2, "DESIGN_TEST_SCENARIO", 2),
    "NO_MUTATION_KNOWLEDGE": (2, "DESIGN_MUTATION", 2),
    "KNOWLEDGE_INCOMPLETE": (1, "UPDATE_KNOWLEDGE", 1),
    "KNOWLEDGE_CONFLICT": (3, "RESOLVE_KNOWLEDGE_CONFLICT", 2),
    "KNOWLEDGE_STALE": (2, "UPDATE_KNOWLEDGE", 2),
    "ENVIRONMENT_BLOCKED": (3, "EXECUTE_BEHAVIOR", 4),
}

TASK_TYPES = ("ANALYZE_SOURCE", "ANALYZE_DEPENDENCIES", "EXTRACT_CONTRACT_KNOWLEDGE",
              "DESIGN_TEST_SCENARIO", "EXECUTE_BEHAVIOR", "VALIDATE_EVIDENCE",
              "DESIGN_MUTATION", "EXECUTE_MUTATION", "INVESTIGATE_FAILURE",
              "RESOLVE_KNOWLEDGE_CONFLICT", "UPDATE_KNOWLEDGE")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_json(path: str, default):
    if not os.path.isfile(path):
        return default
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _analyses() -> dict[tuple[str, str], dict]:
    found = {}
    for path in glob.glob(os.path.join(source_analysis.OUTPUT_DIR, "*", "*.json")):
        record = _load_json(path, {})
        if record:
            found[(record["feature_id"], record["behavior_id"])] = record
    return found


def environment_ready() -> tuple[bool, str]:
    """学习任务的执行能力探测（复用 1.64 的 env_paths，不另造规则）。"""
    try:
        import sys
        sys.path.insert(0, os.path.join(paths.TOOLS_DIR, "validator", "execution"))
        import env_paths  # noqa: PLC0415

        binary = env_paths.find_godot_binary()
        if binary:
            return True, "godot: %s" % binary
        return False, "Godot 可执行文件未找到（GODOT_BIN / 项目配置 / 相邻目录 / PATH 均未命中）"
    except Exception as error:  # noqa: BLE001 - 探测失败本身就是环境阻塞
        return False, "env probe failed: %s" % error


def _knowledge_index(records: list[dict]) -> dict[tuple[str, str], list[dict]]:
    index: dict[tuple[str, str], list[dict]] = {}
    for record in records:
        index.setdefault((record["feature_id"], record["behavior_id"]), []).append(record)
    return index


def _gaps(row: dict, analysis: dict | None, behavior: dict, graph: dict,
          records: list[dict], conflict_ids: set[str], env_ok: bool,
          stale: list[str], scenario_evidenced: bool = False) -> list[dict]:
    gaps = []
    feature_id = row["feature_id"]
    behavior_id = row["behavior_id"]
    key = "%s/%s" % (feature_id, behavior_id)

    if analysis is None:
        gaps.append({"code": "SOURCE_NOT_ANALYZED", "detail": "没有源码分析产物"})
    else:
        status = analysis.get("analysis_status")
        if status == "SOURCE_NOT_FOUND":
            gaps.append({"code": "SOURCE_NOT_FOUND", "detail": "实现文件缺失"})
        elif status == "SOURCE_ENTRY_AMBIGUOUS":
            gaps.append({"code": "SOURCE_ENTRY_AMBIGUOUS",
                         "detail": "；".join(analysis.get("unresolved_questions") or [])[:240]})
        approved_source = [record for record in records
                           if record["knowledge_type"] == "SOURCE_OBSERVATION"
                           and record["verification_status"] == "APPROVED"]
        if not approved_source:
            gaps.append({"code": "CONTRACT_UNDERSTOOD_ONLY",
                         "detail": "只有契约知识，没有已审批的源码观察"})

    outgoing = [edge for edge in graph.get("edges") or []
                if edge["source_behavior"] == key]
    unresolved_requirements = [item for item in graph.get("unresolved_requirements") or []
                               if item["feature_id"] == feature_id]
    if unresolved_requirements or (not outgoing and behavior.get("preconditions")):
        gaps.append({"code": "DEPENDENCY_UNKNOWN",
                     "detail": "契约声明前置/依赖，但没有解析出的依赖边"})

    evidence = row.get("evidence") or {}
    attestation = row.get("attestation") or {}
    if evidence.get("status") != "EVIDENCE_VERIFIED" or \
            attestation.get("status") != "ATTESTATION_VERIFIED":
        gaps.append({"code": "NO_RUNTIME_OBSERVATION",
                     "detail": "evidence=%s attestation=%s"
                               % (evidence.get("status"), attestation.get("status"))})
    # Phase 1.66：真实执行过的场景（VALID + PASSED + EVIDENCE_VERIFIED +
    # ATTESTED_VERIFIED + evaluation VERIFIED_PASS）能消解「没有测试场景」，
    # 依据是 `.ai/learning/scenario_results.json` 里的真实结果，不是手改任务文件。
    if (row.get("evaluation") or {}).get("status") != "VERIFIED_PASS" \
            and not scenario_evidenced:
        gaps.append({"code": "NO_TEST_SCENARIO",
                     "detail": "evaluation=%s" % (row.get("evaluation") or {}).get("status")})
    if (row.get("mutation") or {}).get("status") != "MUTATION_KILLED" and \
            not any(record["knowledge_type"] == "MUTATION_OBSERVATION"
                    and record["verification_status"] == "APPROVED" for record in records):
        gaps.append({"code": "NO_MUTATION_KNOWLEDGE",
                     "detail": "没有 KILLED 的 mutation 知识"})
    if not any(record["verification_status"] == "APPROVED" for record in records):
        gaps.append({"code": "KNOWLEDGE_INCOMPLETE",
                     "detail": "没有已审批的知识（%d 条候选/历史）" % len(records)})
    if conflict_ids:
        gaps.append({"code": "KNOWLEDGE_CONFLICT",
                     "detail": "未解决冲突 %s" % ", ".join(sorted(conflict_ids))})
    if stale:
        gaps.append({"code": "KNOWLEDGE_STALE", "detail": "；".join(stale)})
    if not env_ok and any(code in ("NO_RUNTIME_OBSERVATION", "NO_TEST_SCENARIO")
                          for code in [gap["code"] for gap in gaps]):
        gaps.append({"code": "ENVIRONMENT_BLOCKED", "detail": "Godot 不可用，执行类任务被阻塞"})
    return gaps


def _task_id(feature_id: str, behavior_id: str, task_type: str) -> str:
    return "T-%s-%s-%s" % (feature_id[:10].upper(), behavior_id[:14].upper(),
                           task_type.replace("_", "")[:10])


def scenario_evidence(path: str = "") -> dict[str, dict]:
    """已通过真实执行链的场景，按 feature/behavior 索引（只认四种状态全绿）。"""
    document = _load_json(path or SCENARIO_RESULTS, {})
    index: dict[str, dict] = {}
    for record in document.get("results") or []:
        if record.get("validator_status") != "VALID":
            continue
        if record.get("execution_status") != "PASSED":
            continue
        if record.get("evidence_status") != "EVIDENCE_VERIFIED":
            continue
        if record.get("attestation_status") != "ATTESTED_VERIFIED":
            continue
        if record.get("evaluation_status") != "VERIFIED_PASS":
            continue
        key = "%s/%s" % (record["feature_id"], record["behavior_id"])
        index.setdefault(key, record)
    return index


def build_plan(*, matrix_path: str, graph_path: str = dependencies.GRAPH_PATH,
               out_path: str = PLAN_PATH, label: str = "",
               scenario_results_path: str = "") -> dict:
    matrix = _load_json(matrix_path, None)
    if matrix is None:
        raise SystemExit("matrix not found: %s（必须显式给出，禁止默认扫描评估目录）" % matrix_path)
    graph = _load_json(graph_path, {"edges": [], "unresolved_requirements": []})
    analyses = _analyses()
    records = knowledge_v2.all_records()
    index = _knowledge_index(records)
    open_conflicts = knowledge_v2.conflicts("OPEN")
    env_ok, env_detail = environment_ready()

    executed_scenarios = scenario_evidence(scenario_results_path)

    conflict_by_behavior: dict[tuple[str, str], set[str]] = {}
    for conflict in open_conflicts:
        key = (conflict["feature_id"], conflict["behavior_id"])
        conflict_by_behavior.setdefault(key, set()).add(conflict["conflict_id"])

    upstream_counts: dict[str, int] = {}
    for edge in graph.get("edges") or []:
        upstream_counts[edge["target_behavior"]] = \
            upstream_counts.get(edge["target_behavior"], 0) + 1

    known_types: dict[str, tuple[str, str]] = {}
    for item in paths.supported_behaviors():
        known_types["%s/%s" % (item["feature_id"], item["behavior_id"])] = item["behavior"]

    tasks = []
    excluded = []
    for row in matrix["rows"]:
        feature_id, behavior_id = row["feature_id"], row["behavior_id"]
        key = "%s/%s" % (feature_id, behavior_id)
        behavior_records = index.get((feature_id, behavior_id), [])
        current_version = str(row.get("contract_version") or "")
        stale_reasons = []
        for record in behavior_records:
            if record["verification_status"] not in ("APPROVED", "PENDING_REVIEW"):
                continue
            # 与 extract.py 同口径：implementation_digest = 所有实现文件 digest 的拼接
            scripts = (analyses.get((feature_id, behavior_id)) or {}).get("scripts") or []
            current_digest = "".join(script["digest"] for script in scripts)
            reasons = knowledge_v2.staleness(record, current_contract_version=current_version,
                                             current_implementation_digest=current_digest
                                             if record.get("implementation_digest") else "")
            stale_reasons.extend("%s: %s" % (record["knowledge_id"], reason)
                                 for reason in reasons)
        gaps = _gaps(row, analyses.get((feature_id, behavior_id)), known_types.get(key, {}),
                     graph, behavior_records, conflict_by_behavior.get((feature_id, behavior_id),
                                                                      set()),
                     env_ok, stale_reasons, key in executed_scenarios)
        risk = paths.risk_of(feature_id, behavior_id)
        upstream = min(upstream_counts.get(key, 0), 6)
        has_failure = any(record["knowledge_type"] == "FAILURE_KNOWLEDGE"
                          for record in behavior_records)
        for gap in gaps:
            severity, task_type, cost = GAPS[gap["code"]]
            priority = (3 * severity + risk / 2 + upstream
                        + (2 if has_failure else 0) - cost)
            driven = _driven_by(task_type, behavior_records)
            rationale = ("severity %d×3 + risk %d/2 + upstream %d + failure %d - cost %d = %.1f：%s"
                         % (severity, risk, upstream, 2 if has_failure else 0, cost, priority,
                            gap["detail"]))
            if driven:
                rationale += "\n知识驱动：%s" % "; ".join(driven)
            blocked_by = []
            if not env_ok and task_type in ("EXECUTE_BEHAVIOR", "EXECUTE_MUTATION",
                                            "VALIDATE_EVIDENCE"):
                blocked_by.append("ENVIRONMENT: %s" % env_detail)
            if any(gap_item["code"] == "KNOWLEDGE_CONFLICT"
                   for gap_item in gaps) and task_type != "RESOLVE_KNOWLEDGE_CONFLICT":
                blocked_by.append("有未解决的 KNOWLEDGE_CONFLICT")
            tasks.append({
                "task_id": _task_id(feature_id, behavior_id, task_type),
                "feature_id": feature_id,
                "behavior_id": behavior_id,
                "behavior": key,
                "task_type": task_type,
                "gap": gap["code"],
                "priority": round(priority, 1),
                "rationale": rationale,
                "prerequisites": ([gap["code"]] if gap["code"] != "ENVIRONMENT_BLOCKED" else []),
                "expected_outputs": _expected_outputs(task_type),
                "blocking_conditions": blocked_by,
                "estimated_cost": cost,
                "driven_by_knowledge": [item.split(" ")[0] for item in driven],
                "source_references": _sources(row, analyses.get((feature_id, behavior_id))),
                "status": "BLOCKED" if blocked_by else "PENDING",
            })

    # 已完成任务不重复安排：同类任务已有 APPROVED 知识 → 显式排除并说明
    for key, records in index.items():
        approved_types = {record["knowledge_type"] for record in records
                          if record["verification_status"] == "APPROVED"}
        if "SOURCE_OBSERVATION" in approved_types:
            excluded.append({"behavior": "%s/%s" % key, "task_type": "ANALYZE_SOURCE",
                             "reason": "已有已审批 SOURCE_OBSERVATION"})
        if "MUTATION_OBSERVATION" in approved_types:
            excluded.append({"behavior": "%s/%s" % key, "task_type": "DESIGN_MUTATION",
                             "reason": "已有已审批 MUTATION_OBSERVATION"})

    tasks.sort(key=lambda item: (-item["priority"], item["behavior"], item["task_type"]))
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for task in tasks:
        by_type[task["task_type"]] = by_type.get(task["task_type"], 0) + 1
        by_status[task["status"]] = by_status.get(task["status"], 0) + 1

    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "label": label,
        "inputs": {
            "matrix": os.path.relpath(matrix_path, paths.ROOT).replace(os.sep, "/"),
            "matrix_generated_at": matrix.get("generated_at", ""),
            "graph": os.path.relpath(graph_path, paths.ROOT).replace(os.sep, "/"),
            "analyses": len(analyses),
            "knowledge_records": len(records),
            "approved_records": sum(1 for record in records
                                    if record["verification_status"] == "APPROVED"),
            "environment_ready": env_ok,
            "environment_detail": env_detail,
            "scenario_results": os.path.relpath(
                scenario_results_path or SCENARIO_RESULTS, paths.ROOT).replace(os.sep, "/"),
            "scenario_evidenced_behaviors": len(executed_scenarios),
        },
        "formula": "priority = 3*severity + risk/2 + upstream_impact + failure_bonus - cost",
        "summary": {
            "tasks": len(tasks),
            "by_type": by_type,
            "by_status": by_status,
            "blocked": by_status.get("BLOCKED", 0),
            "excluded_completed": len(excluded),
            "behaviors_with_tasks": len({task["behavior"] for task in tasks}),
        },
        "tasks": tasks,
        "excluded": excluded,
    }


def _driven_by(task_type: str, records: list[dict]) -> list[str]:
    """已审批知识如何塑造任务（用于证明「第一轮知识改变第二轮计划」）。"""
    relevant_types = {
        "DESIGN_MUTATION": ("SOURCE_OBSERVATION", "SCENARIO_OBSERVATION", "BEHAVIOR_OBSERVATION"),
        "DESIGN_TEST_SCENARIO": ("SOURCE_OBSERVATION", "DEPENDENCY_KNOWLEDGE",
                                 "SCENARIO_OBSERVATION"),
        "UPDATE_KNOWLEDGE": ("SOURCE_OBSERVATION", "SCENARIO_OBSERVATION"),
        "ANALYZE_DEPENDENCIES": ("DEPENDENCY_KNOWLEDGE",),
        "INVESTIGATE_FAILURE": ("FAILURE_KNOWLEDGE", "TEST_DESIGN_KNOWLEDGE"),
    }.get(task_type, ())
    notes = []
    for record in records:
        if record["verification_status"] != "APPROVED":
            continue
        if record["knowledge_type"] not in relevant_types:
            continue
        if record["key"] == "guards":
            conditions = [item.get("condition") for item in
                          (record["content"] or {}).get("conditions") or []][:1]
            notes.append("%s 已记录守卫 %s" % (record["knowledge_id"], conditions[0]
                                               if conditions else "(无)"))
        elif record["key"] == "entry_points":
            names = [item.get("name") for item in
                     (record["content"] or {}).get("entry_points") or []][:2]
            notes.append("%s 已记录入口 %s" % (record["knowledge_id"], "/".join(names)))
        elif record["key"] == "dependencies":
            count = (record["content"] or {}).get("count", 0)
            notes.append("%s 已记录 %d 条依赖" % (record["knowledge_id"], count))
        elif record["key"].startswith("scenario:"):
            content = record["content"] or {}
            notes.append("%s 已真实执行场景 %s（%s / evaluation=%s）"
                         % (record["knowledge_id"], content.get("scenario_id", "")[:12],
                            content.get("classification"), content.get("evaluation_status")))
        elif record["key"].startswith("behavior:"):
            content = record["content"] or {}
            notes.append("%s 已观察行为 %s" % (record["knowledge_id"],
                                          content.get("classification")))
        elif record["key"].startswith("test_design:"):
            notes.append("%s 记录了测试设计错误" % record["knowledge_id"])
    return notes


def _expected_outputs(task_type: str) -> list[str]:
    return {
        "ANALYZE_SOURCE": ["source_analysis json", "unresolved_questions"],
        "ANALYZE_DEPENDENCIES": ["dependency edges with source references"],
        "EXTRACT_CONTRACT_KNOWLEDGE": ["CONTRACT_FACT candidates"],
        "DESIGN_TEST_SCENARIO": ["candidate scenario（未执行前不是 Test Observation）"],
        "EXECUTE_BEHAVIOR": ["evidence bundle", "signature", "attestation", "evaluation report"],
        "VALIDATE_EVIDENCE": ["validator verdict"],
        "DESIGN_MUTATION": ["mutation spec with unique anchor"],
        "EXECUTE_MUTATION": ["mutation report（KILLED/SURVIVED/INVALID）"],
        "INVESTIGATE_FAILURE": ["failure knowledge with root cause"],
        "RESOLVE_KNOWLEDGE_CONFLICT": ["conflict resolution record"],
        "UPDATE_KNOWLEDGE": ["approved knowledge record"],
    }.get(task_type, [])


def _sources(row: dict, analysis: dict | None) -> list[str]:
    references = []
    if row.get("contract_version"):
        references.append("contract:%s" % row["contract_version"])
    if analysis:
        references.extend(script["path"] for script in analysis.get("scripts") or [])
    bundle = (row.get("evidence") or {}).get("bundle")
    if bundle:
        references.append(bundle)
    return references


def write_markdown(plan: dict, path: str) -> str:
    lines = ["# Learning Plan（%s）" % (plan.get("label") or plan["generated_at"]), "",
             "优先级公式：`%s`" % plan["formula"], "",
             "任务总数 **%d**，阻塞 **%d**，因已有知识排除 **%d**。"
             % (plan["summary"]["tasks"], plan["summary"]["blocked"],
                plan["summary"]["excluded_completed"]), "",
             "| # | 任务 | 缺口 | 优先级 | 状态 |", "| --- | --- | --- | --- | --- |"]
    for index, task in enumerate(plan["tasks"][:40], start=1):
        lines.append("| %d | %s `%s` | %s | %.1f | %s |"
                     % (index, task["task_type"], task["behavior"], task["gap"],
                        task["priority"], task["status"]))
    lines.append("")
    if plan["excluded"]:
        lines.append("## 已排除（不重复安排）")
        for item in plan["excluded"][:20]:
            lines.append("- `%s` %s：%s" % (item["behavior"], item["task_type"], item["reason"]))
        lines.append("")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Learning planner")
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--graph", default=dependencies.GRAPH_PATH)
    parser.add_argument("--out", default=PLAN_PATH)
    parser.add_argument("--label", default="")
    parser.add_argument("--scenario-results", default="",
                        help="真实场景执行结果（默认 .ai/learning/scenario_results.json）")
    args = parser.parse_args(argv)
    plan = build_plan(matrix_path=args.matrix, graph_path=args.graph, out_path=args.out,
                      label=args.label, scenario_results_path=args.scenario_results)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(plan, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    write_markdown(plan, os.path.splitext(args.out)[0] + ".md")
    print(json.dumps(plan["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
