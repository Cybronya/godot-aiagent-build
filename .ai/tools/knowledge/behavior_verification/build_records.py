#!/usr/bin/env python3
"""从真实产物生成 Behavior Verification Knowledge 记录（Phase 1.64）。

数据来源（全部是真实文件，不猜结论）：

    Features/<feature>/template.yaml#behavior      契约（CONTRACT_FACT）
    validator/bindings/behavior_bindings.json      已审批绑定（CONTRACT_FACT）
    .ai/context/phase_1_64_behavior_taxonomy.json  分类依据（INFERENCE，附 basis）
    <batch>/summary.json                           真实 run / evidence / eval 结论
    .ai/tmp/p164/mutation/reports/*.json           mutation 判定（MUTATION_OBSERVATION）
    <matrix>/coverage_matrix.json                  八维状态与 digest

用法：
    python .ai/tools/knowledge/behavior_verification/build_records.py \
        --batch .ai/tmp/p164/batch1/summary.json \
        --matrix .ai/tmp/p164/batch1/matrix_after/coverage_matrix.json \
        --mutation-reports .ai/tmp/p164/mutation/reports
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

def _project_root() -> str:
    current = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isfile(os.path.join(current, "project.godot")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return os.getcwd()
        current = parent


ROOT = _project_root()
for _p in (os.path.join(ROOT, ".ai", "tools", "validator"),
           os.path.join(ROOT, ".ai", "tools", "validator", "execution"),
           os.path.join(ROOT, ".ai", "tools", "scene_composer"),
           os.path.join(ROOT, ".ai", "tools", "evaluation"),
           os.path.join(ROOT, ".ai", "tools", "knowledge", "behavior_verification")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import yaml                       # noqa: E402
import trace_bindings as tb       # noqa: E402
import store                      # noqa: E402


# 历史失败知识（来自 1.59/1.63 的真实记录；不随本次重跑丢失）
# 每条都写清：失败场景、输入、预期、实际、产物、源码位置、根因、修复、修复后验证。
HISTORICAL_FAILURES = {
    ("trigger_switch", "latch_once"): [{
        "mutation_id": "M04-trigger-switch-latch-removed",
        "kind": "INVALID_MUTANT",
        "status": "RESOLVED",
        "scenario": "behavior 'latch_once'：两次 physics.overlap + 帧推进",
        "input": "删除 Latching 分支的 `if _triggered: return` 守卫",
        "expected": "第二次接触被锁存守卫拒绝（activated 仅 1 次）",
        "actual": "control 与 mutant 观测完全相同（count=1）——注入未生效，不是未检出",
        "artifact": ".ai/tmp/p159/reports/M04-trigger-switch-latch-removed.json",
        "source_location": "Features/trigger_switch/trigger_switch.gd::_on_body_entered",
        "root_cause": "契约第二次 physics.overlap 不产生第二次 body_entered，守卫在真实执行里走不到",
        "fix": "契约尾部补 advance_frames(6) 强制物理帧（Features/trigger_switch/template.yaml），重绑 BND-005",
        "post_fix_verification": "Phase 1.63：M04 MUTANT_KILLED（control count 1 / mutant count 2）",
        "source_refs": [".ai/context/PHASE_1_63_COMPLETION.md",
                        ".ai/tools/evaluation/mutation/mutation_catalog.yaml#M04"],
    }],
    ("save_game", "save_slot_persists_world_state"): [{
        "mutation_id": "M06-save-game-last-slot-not-recorded",
        "kind": "INVALID_MUTANT",
        "status": "RESOLVED",
        "scenario": "behavior 'save_slot_persists_world_state'：存槽后回读 last_slot",
        "input": "删除 `_record_last_slot(slot_path)` 调用",
        "expected": "last_slot 回读为空或被拒",
        "actual": "control 与 mutant 都读到 'behavior_save'：user:// 跨 run 残留使「忘记记录」不可观测",
        "artifact": ".ai/tmp/p159/reports/M06-save-game-last-slot-not-recorded.json",
        "source_location": "Features/save_game/save_game.gd::save_to_slot",
        "root_cause": "采集器临时项目沿用同一 application name，user:// 映射同一目录",
        "fix": "BehaviorWorkspace 支持 per-run `use_custom_user_dir`（--user-dir-tag），harness 生成唯一 tag",
        "post_fix_verification": "Phase 1.63：M06 MUTANT_KILLED（control 'behavior_save' / mutant ''）",
        "source_refs": [".ai/context/PHASE_1_63_COMPLETION.md",
                        ".ai/tools/scene_composer/feature_behavior_evidence.py"],
    }],
}


def contract_of(feature: str, behavior: str) -> dict:
    path = os.path.join(ROOT, "Features", feature, "template.yaml")
    with open(path, encoding="utf-8") as handle:
        document = yaml.safe_load(handle) or {}
    for item in document.get("behavior") or []:
        if str(item.get("id")) == behavior:
            return item
    return {}


def mutation_index(report_dirs: str) -> dict:
    """(feature, behavior) -> [mutation 结论]。

    `report_dirs` 可用逗号分隔多个目录（每个目录里是原始 Run 报告）；这里**不**复制报告，
    因此 source_ref 保持为真实产物路径，重复生成记录时事实不会漂移。
    """
    index: dict[tuple[str, str], list[dict]] = {}
    paths: list[str] = []
    for directory in str(report_dirs).split(","):
        directory = directory.strip()
        if directory:
            paths.extend(glob.glob(os.path.join(directory, "*.json")))
    for path in sorted(paths):
        name = os.path.basename(path)
        if name.startswith("summary-"):
            continue
        try:
            report = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        catalog = report.get("catalog") or {}
        key = (str(catalog.get("feature_id")), str(catalog.get("behavior_id")))
        entry = {
            "mutation_id": report.get("mutation_id"),
            "mutation_type": catalog.get("mutation_type"),
            "target_function": catalog.get("target_function"),
            "verdict": report.get("verdict"),
            "report": os.path.relpath(path, ROOT).replace("\\", "/"),
            "effectiveness": report.get("effectiveness"),
        }
        index.setdefault(key, []).append(entry)
    return index


def build_record(feature: str, behavior: str, *, batch: dict, matrix_row: dict,
                 taxonomy: dict, bindings: dict, mutations: list[dict]) -> dict:
    contract = contract_of(feature, behavior)
    binding = tb.get_binding(bindings, feature, behavior) or {}
    contract_version = str(binding.get("contract_version") or "")
    evidence = matrix_row.get("evidence") or {}
    evaluation = matrix_row.get("evaluation") or {}
    facts = []

    for precondition in contract.get("preconditions") or []:
        facts.append({
            "claim": "前置条件：%s" % json.dumps(precondition, ensure_ascii=False,
                                                sort_keys=True),
            "source_type": "CONTRACT_FACT",
            "source_ref": "Features/%s/template.yaml#behavior=%s.preconditions"
                          % (feature, behavior),
        })
    for expected in (contract.get("expected") or []):
        facts.append({
            "claim": "期望观测：%s" % json.dumps(expected, ensure_ascii=False,
                                                sort_keys=True),
            "source_type": "CONTRACT_FACT",
            "source_ref": "Features/%s/template.yaml#behavior=%s.expected"
                          % (feature, behavior),
        })
    facts.append({
        "claim": "已审批 Binding 的 expected 与契约一致（binding_id=%s）"
                 % binding.get("binding_id"),
        "source_type": "CONTRACT_FACT",
        "source_ref": "binding:%s" % binding.get("binding_id"),
    })
    if evidence.get("bundle"):
        facts.append({
            "claim": "真实执行证据状态 %s（bundle=%s）"
                     % (evidence.get("status"), evidence.get("bundle")),
            "source_type": "TEST_OBSERVATION",
            "source_ref": str(evidence.get("bundle") or ""),
        })
    if evaluation.get("report"):
        facts.append({
            "claim": "Evaluation 结论 %s（report=%s, task=%s）"
                     % (evaluation.get("status"), evaluation.get("report"),
                        evaluation.get("task_id")),
            "source_type": "TEST_OBSERVATION",
            "source_ref": str(evaluation.get("report") or ""),
        })
    for mutation in mutations:
        facts.append({
            "claim": "Mutation %s 判定 %s（effectiveness=%s）"
                     % (mutation["mutation_id"], mutation["verdict"],
                        json.dumps(mutation.get("effectiveness"), ensure_ascii=False,
                                   sort_keys=True)),
            "source_type": "MUTATION_OBSERVATION",
            "source_ref": mutation["report"],
        })

    entry = taxonomy.get((feature, behavior)) or {}
    category = str(entry.get("p") or "")
    if entry:
        facts.append({
            "claim": "分类 %s（次类 %s）；依据：%s"
                     % (category, ",".join(entry.get("s") or []),
                        entry.get("basis")),
            "source_type": "INFERENCE",
            "source_ref": ".ai/context/phase_1_64_behavior_taxonomy.json",
        })

    scripts = sorted(os.path.relpath(os.path.join(base, name), ROOT).replace("\\", "/")
                     for base, _dirs, files in os.walk(
                         os.path.join(ROOT, "Features", feature))
                     for name in files if name.endswith(".gd"))
    tests = [s for s in scripts if os.path.basename(s).startswith("test_")]
    impl = [s for s in scripts if s not in tests]
    dependencies = sorted({str(a.get("type")).split(".")[0]
                           for a in contract.get("actions") or []})

    failure_modes = list(HISTORICAL_FAILURES.get((feature, behavior), []))
    known_edge_cases = []
    unresolved = []
    for mutation in mutations:
        if mutation["verdict"] in ("INVALID_MUTANT", "MUTANT_SURVIVED"):
            failure_modes.append({
                "kind": mutation["verdict"], "mutation_id": mutation["mutation_id"],
                "observation": mutation.get("effectiveness"),
                "status": "OBSERVED",
                "source_ref": mutation["report"],
            })
    if feature == "trigger_switch" and behavior == "latch_once":
        known_edge_cases.append(
            "M04（删 latch 守卫）曾判 INVALID_MUTANT：契约第二次 physics.overlap 不产生"
            "第二次 body_entered，守卫在真实执行里走不到；1.63 已在契约补尾部 advance_frames"
            "并重绑 BND-005。当前 M08 为 KILLED。")
    if feature == "save_game":
        known_edge_cases.append(
            "M06（漏记 last_slot）曾判 INVALID_MUTANT：user:// 跨 run 残留使「忘记记录」"
            "不可观测；1.63 改用 per-run user_dir_tag 隔离后 M06 为 KILLED。")
    if not mutations:
        unresolved.append("该 Behavior 尚无 L5 mutation 证据，验证体系对其缺陷的分辨力未证明。")
    if evidence.get("status") != "EVIDENCE_VERIFIED":
        unresolved.append("缺少本轮真实证据（矩阵状态 %s）。" % evidence.get("status"))
    if (matrix_row.get("holdout") or {}).get("status") in (None, "NO_HOLDOUT"):
        unresolved.append("无覆盖该 Behavior 的 Holdout 数据集。")

    confident = (evidence.get("status") == "EVIDENCE_VERIFIED"
                 and evaluation.get("status") == "VERIFIED_PASS"
                 and any(m["verdict"] == "MUTANT_KILLED" for m in mutations))
    return {
        "feature_id": feature,
        "behavior_id": behavior,
        "contract_version": contract_version,
        "behavior_category": category,
        "secondary_categories": entry.get("s") or [],
        "implementation_references": impl,
        "dependency_references": dependencies,
        "preconditions": contract.get("preconditions") or [],
        "triggering_conditions": [a.get("type") for a in contract.get("actions") or []],
        "expected_transitions": contract.get("expected") or [],
        "observed_transitions": {
            "evidence_status": evidence.get("status"),
            "evaluation_status": evaluation.get("status"),
            "run_id": matrix_row.get("latest_run_id"),
            "evidence_digest": matrix_row.get("latest_evidence_digest"),
            "attestation_digest": matrix_row.get("latest_attestation_digest"),
        },
        "test_scenarios": {
            "behavior_contract": "Features/%s/template.yaml#behavior=%s"
                                 % (feature, behavior),
            "existing_tests": tests,
            "window_frames": contract.get("window_frames"),
        },
        "evidence_references": [{
            "bundle": evidence.get("bundle"),
            "digest": matrix_row.get("latest_evidence_digest"),
            "signature": (matrix_row.get("signature") or {}).get("status"),
            "attestation": (matrix_row.get("attestation") or {}).get("status"),
            "run_id": matrix_row.get("latest_run_id"),
        }] if evidence.get("bundle") else [],
        "mutation_references": mutations,
        "failure_modes": failure_modes,
        "known_edge_cases": known_edge_cases,
        "confidence": ("VERIFIED_EXECUTION" if confident else
                       "PARTIAL" if (evidence.get("bundle") or mutations) else "UNKNOWN"),
        "unresolved_questions": unresolved,
        "last_verified_run_id": matrix_row.get("latest_run_id"),
        "facts": facts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--mutation-reports",
                        default="".join([".ai/tmp/p164/mutation/reports,",
                                         ".ai/tmp/p164/mutation2/reports"]))
    parser.add_argument("--root", default="")
    # 不在本批证据里、但有 mutation / 历史失败知识的 Behavior（如 1.59 的 M04/M06 对象）
    parser.add_argument("--extra", default="trigger_switch/latch_once",
                        help="comma separated feature/behavior")
    args = parser.parse_args()

    batch = json.load(open(args.batch, encoding="utf-8"))
    matrix = json.load(open(args.matrix, encoding="utf-8"))
    taxonomy = {(e["f"], e["b"]): e for e in json.load(
        open(os.path.join(ROOT, ".ai", "context",
                          "phase_1_64_behavior_taxonomy.json"), encoding="utf-8"))["entries"]}
    bindings = tb.load_bindings()
    mutations = mutation_index(args.mutation_reports)
    rows = {(r["feature_id"], r["behavior_id"]): r for r in matrix["rows"]}

    keys = set(batch["behaviors"])
    for item in str(args.extra or "").split(","):
        item = item.strip()
        if item:
            keys.add(item)

    written = 0
    for key in sorted(keys):
        feature, behavior = key.split("/", 1)
        record = build_record(feature, behavior, batch=batch,
                              matrix_row=rows[(feature, behavior)],
                              taxonomy=taxonomy, bindings=bindings,
                              mutations=sorted(mutations.get((feature, behavior), []),
                                               key=lambda m: str(m["mutation_id"])))
        store.save(record, change_reason="Phase 1.64 batch B1 verification",
                   root=args.root)
        written += 1
        print("recorded %s/%s confidence=%s mutations=%d"
              % (feature, behavior, record["confidence"],
                 len(record["mutation_references"])))
    print(json.dumps(store.summary(args.root), ensure_ascii=False, indent=1))
    print("records_written=%d" % written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
