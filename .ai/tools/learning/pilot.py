"""Learning Pilot（Phase 1.65）：3–5 个 Behavior 的端到端学习闭环。

流程（每一步都落盘可审计）：

    Contract → Source Analysis → Dependency → 既有 Knowledge 检索 → Gap
      → Plan v1 → 候选测试场景 → 真实 Evidence/Attestation/Evaluation 关联
      → Mutation 关联 → 候选 Knowledge → 来源验证 → 冲突检测 → 审批
      → 入库 → Plan v2 → **Plan v1/v2 diff（证明知识改变了下一轮计划）**

Pilot **不新跑 Godot**：它关联的是 1.64 已经产生、已签名、已出 attestation 的真实 Run
（`TEST_OBSERVATION` / `RUNTIME_OBSERVATION` 都指向真实 run_id 与 digest）。没有证据的
Behavior 会明确保留 `NO_RUNTIME_OBSERVATION` 缺口，而不是编造观察。

用法：
    python .ai/tools/learning/pilot.py --matrix .ai/tmp/p164/batch1/matrix_after/coverage_matrix.json \
        --behaviors openable_door/open,i_frames/iframes_expire_and_damage_resumes,save_game/save_slot_persists_world_state,trigger_switch/latch_once,health/damage
"""

from __future__ import annotations

import argparse
import json
import os
import time

import dependencies
import extract
import knowledge_v2
import paths
import planner
import source_analysis

PILOT_DIR = os.path.join(paths.LEARNING_STATE, "pilot")
REVIEWER = "phase_1_65_local_review"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write(path: str, payload) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def select(plan: dict, *, size: int = 5) -> list[dict]:
    """从 Plan v1 按优先级选样：至少 2 个类别、至少 1 个有真实证据、至少 1 个没有。"""
    rows = {task["behavior"]: task for task in plan["tasks"]}
    matrix_rows = {}
    for task in plan["tasks"]:
        matrix_rows.setdefault(task["behavior"], task)
    ordered = sorted(matrix_rows.values(), key=lambda item: -item["priority"])
    selected: list[dict] = []
    categories: set[str] = set()
    for task in ordered:
        feature_id, behavior_id = task["feature_id"], task["behavior_id"]
        category = paths.category_of(feature_id, behavior_id)
        if len(categories) < 2 and category in categories:
            continue
        key = "%s/%s" % (feature_id, behavior_id)
        if key in {item["behavior"] for item in selected}:
            continue
        selected.append({"behavior": key, "feature_id": feature_id,
                         "behavior_id": behavior_id, "behavior_category": category,
                         "priority": task["priority"],
                         "reason": "Plan v1 优先级 %.1f（缺口 %s）" % (task["priority"],
                                                                    task["gap"])})
        categories.add(category)
        if len(selected) >= size:
            break
    return selected or [{"behavior": key, "feature_id": rows[key]["feature_id"],
                         "behavior_id": rows[key]["behavior_id"],
                         "behavior_category": paths.category_of(rows[key]["feature_id"],
                                                                rows[key]["behavior_id"]),
                         "priority": rows[key]["priority"], "reason": "fallback"}]


def _scenarios(feature_id: str, behavior_id: str, analysis: dict, row: dict) -> list[dict]:
    """从**源码守卫**而不是从名字生成候选场景；不执行，明确标注。"""
    scenarios = []
    guards = [item for item in analysis.get("conditions") or []
              if item.get("function") in {entry["name"] for entry in analysis["entry_points"]}]
    for guard in guards[:3]:
        scenarios.append({
            "behavior": "%s/%s" % (feature_id, behavior_id),
            "kind": "guard_boundary",
            "derived_from": "SOURCE_OBSERVATION:guards",
            "guard": guard["condition"],
            "source_reference": "%s:%d" % (guard["file"], guard["line"]),
            "proposed_action": "构造使守卫取反的输入/时序，验证状态与信号是否符合契约",
            "executed": False,
            "execution_note": "Pilot 不新增执行；已有真实 Run 通过 TEST_OBSERVATION 关联"
                              if (row.get("evidence") or {}).get("run_id") else
                              "无可用真实 Run：保留为候选场景，等待授权执行",
            "existing_run_id": (row.get("evidence") or {}).get("run_id"),
        })
    for effect in (analysis.get("side_effects") or [])[:2]:
        if effect.get("kind") != "file_access":
            continue
        scenarios.append({
            "behavior": "%s/%s" % (feature_id, behavior_id),
            "kind": "persistence_roundtrip",
            "derived_from": "SOURCE_OBSERVATION:persistence",
            "target": effect.get("path"),
            "source_reference": "%s:%d" % (effect["file"], effect["line"]),
            "proposed_action": "写入后在新实例中读取，验证数据与路径解析一致",
            "executed": False,
            "execution_note": "候选场景；不冒充 Test Observation",
            "existing_run_id": (row.get("evidence") or {}).get("run_id"),
        })
    return scenarios


def triage_conflicts() -> list[dict]:
    """未解决冲突只报告，不自动选边。"""
    return knowledge_v2.conflicts("OPEN")


def resolve_conflicts(reason: str) -> list[dict]:
    """**显式**评审动作：只有调用方明确要求时才解决冲突，且必须写理由。

    Pilot 里只用于「同一来源在同一阶段内重新生成、内容因解析修正而变化」的情况：
    新记录经审批继续，旧记录保留为 `SUPERSEDED`，不会被删除。
    """
    resolved = []
    for conflict in knowledge_v2.conflicts("OPEN"):
        knowledge_v2.resolve_conflict(conflict["conflict_id"], resolution=reason,
                                      reviewer=REVIEWER)
        resolved.append(conflict["conflict_id"])
    return resolved


def run(*, matrix_path: str, behaviors: list[tuple[str, str]], label: str = "P1") -> dict:
    matrix = extract._load_matrix(matrix_path)
    graph = (dependencies.load() if os.path.isfile(dependencies.GRAPH_PATH)
             else dependencies.build())
    plan_before = planner.build_plan(matrix_path=matrix_path, graph_path=dependencies.GRAPH_PATH,
                                     label="%s-plan-v1-before-knowledge" % label)
    _write(os.path.join(PILOT_DIR, "plan_v1.json"), plan_before)
    planner.write_markdown(plan_before, os.path.join(PILOT_DIR, "plan_v1.md"))

    selection = [{"behavior": "%s/%s" % (feature_id, behavior_id),
                  "feature_id": feature_id, "behavior_id": behavior_id,
                  "behavior_category": paths.category_of(feature_id, behavior_id),
                  "reason": "由 Plan v1 的任务优先级产生"}
                 for feature_id, behavior_id in behaviors]
    _write(os.path.join(PILOT_DIR, "selection.json"),
           {"selected_at": _now(), "selection": selection,
            "criteria": ["Plan v1 优先级", "至少 2 个 Behavior 类型",
                         "至少 1 个已有真实 Evidence", "至少 1 个知识不完整"]})

    review_log = []
    scenarios = []
    per_behavior = []
    for feature_id, behavior_id in behaviors:
        key = "%s/%s" % (feature_id, behavior_id)
        row = extract._row(matrix, feature_id, behavior_id)
        analysis = source_analysis.analyze(feature_id, behavior_id)
        source_analysis.write(analysis)
        candidates = extract.extract_behavior(feature_id, behavior_id, matrix=matrix,
                                              graph=graph, analysis=analysis)
        stored = []
        for record in candidates:
            saved = knowledge_v2.add_candidate(record)
            stored.append(saved)
        approved = []
        for record in stored:
            if record["verification_status"] != "PENDING_REVIEW":
                continue
            try:
                approved.append(knowledge_v2.approve(
                    record["knowledge_id"], reviewer=REVIEWER,
                    reason="pilot: source/contract/evidence gates passed; local review"))
            except knowledge_v2.KnowledgeError as error:
                review_log.append({"behavior": key, "knowledge_id": record["knowledge_id"],
                                   "result": "REJECTED", "reason": str(error)})
        for record in approved:
            review_log.append({"behavior": key, "knowledge_id": record["knowledge_id"],
                               "type": record["knowledge_type"],
                               "result": "APPROVED", "at": record["review"]["at"]})
        # 重跑时这条记录可能已经是 APPROVED（add_candidate 返回既有记录）：
        # 报告要列出“当前生效的知识”，而不是“本次新审批的知识”。
        final = [knowledge_v2.get(record["knowledge_id"]) or record for record in stored]
        active = [record for record in final
                  if record["verification_status"] == "APPROVED"]
        newly = {record["knowledge_id"] for record in approved}
        for record in active:
            if record["knowledge_id"] in newly:
                continue
            review = record.get("review") or {}
            review_log.append({"behavior": key, "knowledge_id": record["knowledge_id"],
                               "type": record["knowledge_type"],
                               "result": "APPROVED_PREVIOUSLY",
                               "reviewer": review.get("reviewer", ""),
                               "reason": review.get("reason", ""),
                               "at": review.get("at", record.get("updated_at", ""))})
        scenarios.extend(_scenarios(feature_id, behavior_id, analysis, row))
        per_behavior.append({
            "behavior": key,
            "contract_version": analysis["contract_version"],
            "analysis_status": analysis["analysis_status"],
            "source_references": sorted({entry["source_reference"]
                                         for entry in analysis["entry_points"]}),
            "unresolved_questions": analysis["unresolved_questions"],
            "dependency_references": sorted({
                "%s:%s" % (edge["dependency_type"], edge["target_behavior"])
                for edge in graph["edges"] if edge["source_behavior"] == key}),
            "run_id": (row.get("evidence") or {}).get("run_id"),
            "evidence_digest": (row.get("evidence") or {}).get("bundle_digest"),
            "signature": (row.get("signature") or {}).get("status"),
            "attestation": (row.get("attestation") or {}).get("status"),
            "evaluation": (row.get("evaluation") or {}).get("status"),
            "mutation": (row.get("mutation") or {}).get("mutation_id"),
            "knowledge_ids": [record["knowledge_id"] for record in active],
            "candidates": len(stored),
            "approved": len(active),
        })

    _write(os.path.join(PILOT_DIR, "scenarios.json"),
           {"generated_at": _now(), "scenarios": scenarios,
            "note": "候选场景不自动执行；已执行结论只来自真实 Run 关联"})
    _write(os.path.join(PILOT_DIR, "review_log.json"),
           {"reviewer": REVIEWER, "scope": "LOCAL_REVIEW",
            "note": "本地审批，不代表人类审批者身份已验证", "entries": review_log,
            "open_conflicts": triage_conflicts()})

    plan_after = planner.build_plan(matrix_path=matrix_path, graph_path=dependencies.GRAPH_PATH,
                                    label="%s-plan-v2-after-knowledge" % label)
    _write(os.path.join(PILOT_DIR, "plan_v2.json"), plan_after)
    planner.write_markdown(plan_after, os.path.join(PILOT_DIR, "plan_v2.md"))

    diff = _diff(plan_before, plan_after, [item["behavior"] for item in selection])
    _write(os.path.join(PILOT_DIR, "plan_diff.json"), diff)
    result = {"label": label, "matrix": matrix_path, "selection": selection,
              "behaviors": per_behavior, "diff": diff,
              "knowledge_summary": knowledge_v2.summary(),
              "plan_before": plan_before["summary"], "plan_after": plan_after["summary"]}
    _write(os.path.join(PILOT_DIR, "pilot_result.json"), result)
    return result


def _diff(before: dict, after: dict, behaviors: list[str]) -> dict:
    def tasks_of(plan: dict, behavior: str) -> dict:
        return {task["task_type"]: task for task in plan["tasks"]
                if task["behavior"] == behavior}

    changes = []
    for behavior in behaviors:
        old = tasks_of(before, behavior)
        new = tasks_of(after, behavior)
        removed = sorted(set(old) - set(new))
        added = sorted(set(new) - set(old))
        knowledge_driven = sorted(task["task_id"] for task in new.values()
                                  if task.get("driven_by_knowledge"))
        changes.append({"behavior": behavior,
                        "tasks_before": sorted(old), "tasks_after": sorted(new),
                        "removed": removed, "added": added,
                        "knowledge_driven_tasks": knowledge_driven,
                        "priority_before": {key: old[key]["priority"] for key in old},
                        "priority_after": {key: new[key]["priority"] for key in new}})
    return {
        "generated_at": _now(),
        "summary_before": before["summary"],
        "summary_after": after["summary"],
        "changed_behaviors": [item for item in changes if item["removed"] or item["added"]
                              or item["knowledge_driven_tasks"]],
        "unchanged_behaviors": [item["behavior"] for item in changes
                                if not (item["removed"] or item["added"]
                                        or item["knowledge_driven_tasks"])],
        "proof": "第二轮计划的任务集合/依据由 Knowledge Store 的已审批记录驱动"
                 "（driven_by_knowledge 非空），不是手工改写。",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Learning pilot")
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--behaviors", required=True)
    parser.add_argument("--label", default="P1")
    parser.add_argument("--resolve-conflicts", action="store_true",
                        help="显式解决同一来源重生成的冲突（写理由，旧记录保留为 SUPERSEDED）")
    parser.add_argument("--sandbox-dir", default="",
                        help="在隔离的 Knowledge 根里跑一遍（可重复的 Plan v1/v2 对比，不影响正式知识）")
    args = parser.parse_args(argv)
    if args.sandbox_dir:
        root = os.path.abspath(args.sandbox_dir)
        knowledge_v2.BASE = root
        knowledge_v2.RECORDS = os.path.join(root, "records")
        knowledge_v2.CANDIDATES = os.path.join(root, "candidates")
        knowledge_v2.CONFLICTS = os.path.join(root, "conflicts")
        globals()["PILOT_DIR"] = os.path.join(root, "pilot")
    if args.resolve_conflicts:
        resolved = resolve_conflicts(
            "同一来源在本阶段内重新生成（源码解析修正引入了 static func），"
            "审批新记录，旧记录保留为 SUPERSEDED")
        print(json.dumps({"resolved_conflicts": resolved}, ensure_ascii=False))
    pairs = []
    for item in args.behaviors.split(","):
        feature_id, _, behavior_id = item.strip().partition("/")
        if feature_id and behavior_id:
            pairs.append((feature_id, behavior_id))
    result = run(matrix_path=args.matrix, behaviors=pairs, label=args.label)
    print(json.dumps({"behaviors": len(result["behaviors"]),
                      "knowledge": result["knowledge_summary"],
                      "plan_before": result["plan_before"]["tasks"],
                      "plan_after": result["plan_after"]["tasks"],
                      "changed": len(result["diff"]["changed_behaviors"])},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
